-- Fix get_top_talkers function
DROP FUNCTION IF EXISTS get_top_talkers(timestamptz, timestamptz, integer);

CREATE OR REPLACE FUNCTION get_top_talkers(
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    top_n INTEGER DEFAULT 10
)
RETURNS TABLE (
    source_ip INET,
    total_bytes NUMERIC,
    total_packets NUMERIC,
    flow_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        fr.source_ip,
        SUM(fr.bytes) AS total_bytes,
        SUM(fr.packets) AS total_packets,
        COUNT(*) AS flow_count
    FROM flow_records fr
    WHERE fr.time BETWEEN start_time AND end_time
    GROUP BY fr.source_ip
    ORDER BY total_bytes DESC
    LIMIT top_n;
END;
$$ LANGUAGE plpgsql;
