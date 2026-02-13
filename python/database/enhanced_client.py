"""
Enhanced Database Client with Error Handling and Performance Optimizations
Production-grade PostgreSQL/TimescaleDB client
"""

import psycopg2
from psycopg2 import pool, sql, extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database errors"""
    pass


class ConnectionError(DatabaseError):
    """Database connection errors"""
    pass


class QueryError(DatabaseError):
    """Query execution errors"""
    pass


class DatabaseClient:
    """
    Enhanced database client with connection pooling,
    error handling, retries, and performance optimizations
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        min_connections: int = 5,
        max_connections: int = 20,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize database client with connection pool
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
            max_retries: Maximum retry attempts for failed operations
            retry_delay: Delay between retries in seconds
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                min_connections,
                max_connections,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=10,
                options='-c statement_timeout=30000'  # 30 second query timeout
            )
            logger.info(f"Database connection pool initialized ({min_connections}-{max_connections} connections)")
        except psycopg2.Error as e:
            raise ConnectionError(f"Failed to create connection pool: {e}")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for getting database connections
        Automatically returns connection to pool
        """
        conn = None
        try:
            conn = self.pool.getconn()
            if conn is None:
                raise ConnectionError("Failed to get connection from pool")
            yield conn
        except psycopg2.OperationalError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Database connection failed: {e}")
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def execute_with_retry(self, operation, *args, **kwargs):
        """
        Execute operation with automatic retry on failure
        
        Args:
            operation: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Result from operation
        
        Raises:
            DatabaseError: After all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    logger.warning(f"Operation failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Operation failed after {self.max_retries} attempts: {e}")
        
        raise DatabaseError(f"Operation failed after {self.max_retries} retries: {last_exception}")
    
    def bulk_insert_flows(
        self,
        flows: List[Tuple],
        batch_size: int = 10000
    ) -> Tuple[int, int]:
        """
        Bulk insert flow records with batching and error handling
        
        Args:
            flows: List of flow tuples
            batch_size: Number of records per batch
        
        Returns:
            Tuple of (successful_inserts, failed_inserts)
        """
        successful = 0
        failed = 0
        
        def _insert_batch(batch):
            nonlocal successful, failed
            
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    
                    # Use COPY for maximum performance
                    cursor.execute("CREATE TEMP TABLE flow_temp (LIKE flow_records INCLUDING DEFAULTS) ON COMMIT DROP;")
                    
                    # Prepare data
                    extras.execute_values(
                        cursor,
                        """
                        INSERT INTO flow_temp VALUES %s
                        """,
                        batch,
                        page_size=1000
                    )
                    
                    # Insert from temp table (handles conflicts)
                    cursor.execute("""
                        INSERT INTO flow_records 
                        SELECT * FROM flow_temp
                        ON CONFLICT DO NOTHING;
                    """)
                    
                    conn.commit()
                    successful += len(batch)
                    logger.debug(f"Inserted batch of {len(batch)} flows")
                    
                except psycopg2.Error as e:
                    conn.rollback()
                    failed += len(batch)
                    logger.error(f"Batch insert failed: {e}")
                    raise QueryError(f"Batch insert failed: {e}")
                finally:
                    cursor.close()
        
        # Process in batches
        for i in range(0, len(flows), batch_size):
            batch = flows[i:i + batch_size]
            try:
                self.execute_with_retry(_insert_batch, batch)
            except DatabaseError as e:
                logger.error(f"Failed to insert batch {i//batch_size + 1}: {e}")
                continue
        
        logger.info(f"Bulk insert complete: {successful} success, {failed} failed")
        return successful, failed
    
    def query_with_timeout(
        self,
        query: str,
        params: Optional[Tuple] = None,
        timeout: int = 30
    ) -> List[Dict]:
        """
        Execute query with timeout and return results as list of dicts
        
        Args:
            query: SQL query
            params: Query parameters
            timeout: Timeout in seconds
        
        Returns:
            List of result dictionaries
        """
        def _execute_query():
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                    cursor.execute(f"SET statement_timeout = {timeout * 1000};")
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    cursor.close()
                    return results
                except psycopg2.errors.QueryCanceled:
                    raise QueryError(f"Query timed out after {timeout} seconds")
                except psycopg2.Error as e:
                    raise QueryError(f"Query failed: {e}")
        
        return self.execute_with_retry(_execute_query)
    
    def get_top_talkers(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get top traffic sources with error handling
        
        Args:
            start_time: Start time
            end_time: End time
            limit: Number of results
        
        Returns:
            List of top talkers
        """
        query = """
            SELECT 
                source_ip,
                SUM(bytes) as total_bytes,
                SUM(packets) as total_packets,
                COUNT(*) as flow_count
            FROM flow_records
            WHERE time BETWEEN %s AND %s
            GROUP BY source_ip
            ORDER BY total_bytes DESC
            LIMIT %s;
        """
        
        try:
            return self.query_with_timeout(query, (start_time, end_time, limit))
        except QueryError as e:
            logger.error(f"Failed to get top talkers: {e}")
            return []
    
    def get_interface_utilization(
        self,
        device_id: Optional[str] = None,
        minutes: int = 60
    ) -> List[Dict]:
        """
        Get interface utilization metrics
        
        Args:
            device_id: Optional device ID filter
            minutes: Time window in minutes
        
        Returns:
            List of interface metrics
        """
        query = """
            SELECT 
                i.interface_name,
                d.hostname,
                im.utilization_percent,
                im.bytes_in,
                im.bytes_out,
                im.time
            FROM interface_metrics im
            JOIN network_interfaces i ON im.interface_id = i.interface_id
            JOIN network_devices d ON i.device_id = d.device_id
            WHERE im.time > NOW() - INTERVAL '%s minutes'
        """
        
        params = [minutes]
        
        if device_id:
            query += " AND d.device_id = %s"
            params.append(device_id)
        
        query += " ORDER BY im.time DESC LIMIT 100;"
        
        try:
            return self.query_with_timeout(query, tuple(params))
        except QueryError as e:
            logger.error(f"Failed to get interface utilization: {e}")
            return []
    
    def health_check(self) -> bool:
        """
        Check database health
        
        Returns:
            True if database is healthy
        """
        try:
            result = self.query_with_timeout("SELECT 1;", timeout=5)
            return len(result) == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_pool_stats(self) -> Dict:
        """
        Get connection pool statistics
        
        Returns:
            Dictionary with pool stats
        """
        try:
            pool = self.pool
            return {
                'total_connections': len(pool._pool) + len(pool._used),
                'available_connections': len(pool._pool),
                'used_connections': len(pool._used),
                'min_connections': pool.minconn,
                'max_connections': pool.maxconn
            }
        except Exception as e:
            logger.error(f"Failed to get pool stats: {e}")
            return {}
    
    def close(self):
        """Close all connections in pool"""
        try:
            self.pool.closeall()
            logger.info("Database connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")


# Example usage and testing
if __name__ == "__main__":
    # Configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'netweaver',
        'user': 'netweaver',
        'password': 'netweaver_secure_pass_2026',
        'min_connections': 2,
        'max_connections': 10
    }
    
    try:
        # Initialize client
        print("Initializing database client...")
        client = DatabaseClient(**db_config)
        
        # Health check
        print("\nPerforming health check...")
        if client.health_check():
            print("✓ Database is healthy")
        else:
            print("✗ Database health check failed")
        
        # Pool stats
        print("\nConnection pool stats:")
        stats = client.get_pool_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Query test
        print("\nTesting query...")
        from datetime import timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        top_talkers = client.get_top_talkers(start_time, end_time, limit=5)
        print(f"✓ Retrieved {len(top_talkers)} top talkers")
        
        # Cleanup
        client.close()
        print("\n✓ All tests passed!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
