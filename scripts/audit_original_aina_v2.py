"""Same frozen v1 census; authenticated draft-access adapter v2."""
from pathlib import Path
import audit_original_aina_v1 as audit

audit.CONFIG = Path('configs/original_aina_audit_v2.json')

if __name__ == '__main__':
    try:
        audit.main()
    except Exception as exc:
        audit.save(audit.OUT/'failure.json', {'type': type(exc).__name__, 'message': str(exc)})
        raise
