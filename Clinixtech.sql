-- Run as SYSTEM user first to clean up

-- =====================================================================
-- =====================================================================
-- SE-204 EVALUATION SCRIPTS (LIVE DEMONSTRATION)
-- =====================================================================
-- =====================================================================


-- =====================================================================
-- PHASE 1: MASSIVE DATA GENERATION (RUN THIS BEFORE THE EVALUATOR ARRIVES)
-- Generates 15,000+ rows to prove the database handles high loads and 
-- forces the Oracle Cost-Based Optimizer to utilize our B-Tree indexes.
-- =====================================================================
SET SERVEROUTPUT ON;

DECLARE
    TYPE id_array IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
    v_doc_ids id_array;
    v_pat_ids id_array;
    
    v_apt_id NUMBER;
    v_status VARCHAR2(20);
    v_priority VARCHAR2(20);
    v_amount NUMBER;
    v_random_doc NUMBER;
    v_random_pat NUMBER;
BEGIN
    SELECT id BULK COLLECT INTO v_doc_ids FROM doctor;
    SELECT id BULK COLLECT INTO v_pat_ids FROM patient;
    
    IF v_doc_ids.COUNT = 0 OR v_pat_ids.COUNT = 0 THEN
        DBMS_OUTPUT.PUT_LINE('ERROR: Please register at least 1 Doctor and 1 Patient via UI first!');
        RETURN;
    END IF;

    DBMS_OUTPUT.PUT_LINE('Starting massive data generation...');

    FOR i IN 1..15000 LOOP
        v_apt_id := appointment_id_seq.NEXTVAL;
        v_random_doc := v_doc_ids(TRUNC(DBMS_RANDOM.VALUE(1, v_doc_ids.COUNT + 1)));
        v_random_pat := v_pat_ids(TRUNC(DBMS_RANDOM.VALUE(1, v_pat_ids.COUNT + 1)));
        
        IF DBMS_RANDOM.VALUE < 0.2 THEN v_priority := 'Emergency';
        ELSIF DBMS_RANDOM.VALUE < 0.5 THEN v_priority := 'Urgent';
        ELSE v_priority := 'Normal'; END IF;
        
        IF DBMS_RANDOM.VALUE < 0.7 THEN v_status := 'completed';
        ELSIF DBMS_RANDOM.VALUE < 0.9 THEN v_status := 'pending';
        ELSE v_status := 'cancelled'; END IF;

        INSERT INTO appointment (id, patient_id, doctor_id, appointment_date, time_slot, priority, status)
        VALUES (v_apt_id, v_random_pat, v_random_doc, SYSDATE - DBMS_RANDOM.VALUE(1, 365), '10:00 AM', v_priority, v_status);

        v_amount := ROUND(DBMS_RANDOM.VALUE(1000, 5000), -2); 
        INSERT INTO payment (id, patient_id, appointment_id, amount, payment_date, payment_status)
        VALUES (payment_id_seq.NEXTVAL, v_random_pat, v_apt_id, v_amount, SYSDATE - DBMS_RANDOM.VALUE(1, 365), 
                CASE WHEN v_status = 'completed' THEN 'Paid' ELSE 'Pending' END);
    END LOOP;
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('SUCCESS: 15,000 Appointments and Payments have been seeded!');
END;
/


-- =====================================================================
-- PHASE 2: COMPLEX ANALYTICAL QUERY (RUN DURING DEMO - RUBRIC 5/5)
-- Finds top-performing doctors who have handled 'Emergency' patients.
-- Features: INNER JOIN, LEFT JOIN, Nested Subqueries, Aggregation (SUM/COUNT).
-- =====================================================================
SELECT 
    d.id AS doctor_id, 
    d.name AS doctor_name, 
    d.specialization,
    COUNT(a.id) AS total_appointments,
    SUM(p.amount) AS total_revenue,
    (SELECT COUNT(*) FROM appointment a2 WHERE a2.doctor_id = d.id AND a2.status = 'completed') AS completed_cases
FROM doctor d
INNER JOIN appointment a ON d.id = a.doctor_id
LEFT JOIN payment p ON a.id = p.appointment_id
WHERE d.id IN (
    -- Nested Subquery: Only include doctors who have handled emergencies
    SELECT DISTINCT doctor_id
    FROM appointment
    WHERE priority = 'Emergency'
)
GROUP BY d.id, d.name, d.specialization
ORDER BY total_revenue DESC NULLS LAST;


-- =====================================================================
-- PHASE 3: LIVE OPTIMIZATION DEMONSTRATION (RUN DURING DEMO - RUBRIC 5/5)
-- =====================================================================

-- STEP A: Run this to show the unoptimized "TABLE ACCESS FULL" (Scanning 15,000 rows)
EXPLAIN PLAN FOR 
SELECT * FROM appointment WHERE doctor_id = 5 AND status = 'pending';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);


-- STEP B: Run these to create the B-Tree Composite Indexes live
CREATE INDEX idx_apt_doc_status ON appointment(doctor_id, status);
CREATE INDEX idx_apt_priority ON appointment(priority);
CREATE INDEX idx_pay_apt ON payment(appointment_id);


-- STEP C: Run Step A again to show the optimized "INDEX RANGE SCAN" (O(log N) Time Complexity)
EXPLAIN PLAN FOR 
SELECT * FROM appointment WHERE doctor_id = 5 AND status = 'pending';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

-- =========================== END OF SCRIPT ===========================






