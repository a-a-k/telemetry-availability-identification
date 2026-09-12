"""Unchanged primary verifier with both original and amended source locks."""
from . import v4_confirmation_verification_v1 as fixed
from .v4_confirmation_orchestration_v2 import verify_new_locks

if __name__=='__main__':
    fixed.verify_new_locks=verify_new_locks
    fixed.main()
