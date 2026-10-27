"""Local source audit: verify packaged stimuli against only the frozen A2 study split."""
import csv
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
A2 = BASE.parents[1] / 'Assignment-2'

def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def audit():
    manifest=json.loads((BASE/'data/study_manifest.json').read_text())
    items=manifest['items'];study=rows(A2/'data/study.csv')
    ai={int(row['study_index']):row for row in rows(A2/'studySet_ai_outputs/study_ai_outputs.csv')}
    expected={(r['brand'],r['label'],r['file_name']) for r in study}
    actual={(r['brand'],r['ground_truth'],r['source_file']) for r in items}
    require(len(items)==len(study)==len(ai)==len(actual)==200,'Expected exactly 200 study entries.')
    require(expected==actual,'Packaged items do not exactly match the study split.')
    names=set()
    for item in items:
        original=A2/'data/clean_data'/f"{item['brand']}_{item['ground_truth']}"/item['source_file']
        overlay=A2/ai[item['study_index']]['gradcam_path']
        for source,name in [(original,item['original']),(overlay,item['gradcam'])]:
            packaged=BASE/'data/stimuli'/name
            require(hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(packaged.read_bytes()).digest(),f'Asset differs from study source: {name}')
            names.add(name)
        reference=ai[item['study_index']]
        require(item['ai_prediction']==reference['ai_prediction'],'AI prediction mismatch.')
        for field in ('ai_confidence','calibrated_fake_probability','raw_fake_probability'):
            require(item[field]==float(reference[field]),f'AI {field} mismatch.')
    require(names=={p.name for p in (BASE/'data/stimuli').iterdir() if p.is_file()},'Unexpected packaged assets.')
    for split in ('train','validation','test'):
        other={(r['brand'],r['label'],r['file_name']) for r in rows(A2/'data'/f'{split}.csv')}
        require(not expected.intersection(other),f'Study identities overlap with {split}.')
    return dict(study_photos=200,study_gradcam_overlays=200,byte_matched_assets=400,extra_images=0,
                train_validation_test_overlap=0,dataset_version=manifest['version'])

if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
