# Database migration notes

This patch changes Python code only and does not add tables or columns. It retains the existing startup `init_db` schema synchronization behavior. Make an encrypted backup of existing databases before updating. Never use a real patient database for automated tests. The existing schema synchronization has not been independently tested for reversibility; do not assume it is a reversible migration framework.
