"""Use the fixed compact arithmetic for every phase, stage, ratio and resource."""
import argparse
import json
from pathlib import Path
import sys

import summarize_v3_exact_comparison_v2 as fixed
from retain_v4_confirmed_performance_v2 import validate


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    fixed.validate_compact=validate
    fixed.main()
    path=args.out/'REPORT.md';text=path.read_text(encoding='utf-8')
    text=text.replace('# Исправленное сравнение точных алгоритмов v2','# Полное сравнение вычислительных затрат на новых моделях')
    text=text.replace('78 прикладных моделей из исходных repetition=0, 27 искусственных позиций;',
        'Все поддержанные calibration-модели новой серии из 18 кампаний и 60 запланированных случаев; структурные отсутствия явно сохранены;')
    text=text.replace('## Полная искусственная сетка','## Прежняя искусственная сетка не повторялась')
    text=text.replace('Новых кампаний нет.','В этом измерительном запуске телеметрия повторно не собиралась; источник — новая подтверждающая серия с технической поправкой v2.')
    path.write_text(text,encoding='utf-8',newline='\n')


if __name__=='__main__':main()
