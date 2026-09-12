"""Technical capture repair; original event, inference and verdicts stay fixed."""
import os
from pathlib import Path
import sys

from . import v3_comparison_acquisition_v1 as acquisition
from . import v4_primary_capture_v1 as capture
from . import v4_retry_controls_v1 as controls
from .v3_primary_projection import write
from .v4_retry_controls_v2 import run


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true': raise ValueError('real capture is remote only')
    out=Path(sys.argv[sys.argv.index('--out')+1]).resolve()
    bundle=Path(sys.argv[sys.argv.index('--bundle')+1]).resolve() if '--bundle' in sys.argv else Path('workflow-input/petclinic-build').resolve()
    original_period=acquisition.petclinic_period
    def checkpoint(*args,**kwargs):
        result=original_period(*args,**kwargs)
        period=args[5] if len(args)>5 else kwargs['period']
        rows,health,events,metadata=result
        write(out/'period-checkpoints'/(period+'.json'),dict(requests=rows,health=health,events=events,metadata=metadata))
        return result
    acquisition.petclinic_period=checkpoint
    controls.run=run
    capture.install(out,bundle)
    acquisition.main()


if __name__=='__main__':main()
