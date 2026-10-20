"""Additive visit migration. Run from project root; repeat runs are safe.
Adds medications.instructions, consultation_plans and outpatient_appointments.
Existing clinical/dispensing rows are retained. Uses the configured DATABASE_URL.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.database import init_db
if __name__=='__main__':
    init_db()
    print('Additive consultation decisions migration completed.')
