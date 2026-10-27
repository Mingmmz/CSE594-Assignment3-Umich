"""Package only the frozen A2 study split. No training or prediction changes."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent
A2 = BASE.parents[1] / 'Assignment-2'

def prepare():
    source = A2 / 'studySet_ai_outputs/study_ai_outputs.csv'
    rows = list(csv.DictReader(source.open()))
    study = list(csv.DictReader((A2 / 'data/study.csv').open()))
    if len(rows) != 200 or len(study) != 200:
        raise ValueError('Expected exactly 200 frozen study items.')
    expected = {(r['brand'], r['label'], r['file_name']) for r in study}
    actual = {(r['brand'], r['ground_truth'], r['file_name']) for r in rows}
    if expected != actual or len(actual) != 200:
        raise ValueError('Study manifest and AI outputs do not match exactly.')
    assets = BASE / 'data/stimuli'
    assets.mkdir(parents=True, exist_ok=True)
    items = []
    for r in rows:
        identity = f"{r['study_index']}:{r['brand']}:{r['file_name']}"
        item_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
        original = A2 / 'data/clean_data' / f"{r['brand']}_{r['ground_truth']}" / r['file_name']
        cam = A2 / r['gradcam_path']
        original_name = item_id + original.suffix.lower()
        cam_name = item_id + '-cam.png'
        if not original.is_file() or not cam.is_file():
            raise FileNotFoundError('Missing study original or Grad-CAM: ' + identity)
        shutil.copyfile(original, assets / original_name)
        shutil.copyfile(cam, assets / cam_name)
        confidence = float(r['ai_confidence'])
        probability = float(r['calibrated_fake_probability'])
        prediction = r['ai_prediction']
        assert prediction in ('genuine', 'fake')
        assert prediction == ('fake' if probability >= .5 else 'genuine')
        assert abs(confidence - (probability if prediction == 'fake' else 1-probability)) < 1e-5
        items.append(dict(item_id=item_id, study_index=int(r['study_index']),
                          brand=r['brand'], ground_truth=r['ground_truth'],
                          source_file=r['file_name'], original=original_name, gradcam=cam_name,
                          ai_prediction=prediction, ai_confidence=confidence,
                          calibrated_fake_probability=probability,
                          raw_fake_probability=float(r['raw_fake_probability'])))
    config = json.loads((A2 / 'results/calibration_config.json').read_text())
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(assets.iterdir()) if p.is_file()}
    version = hashlib.sha256(json.dumps([items, config, checksums], sort_keys=True).encode()).hexdigest()
    manifest = dict(version=version, model=config, items=items, checksums=checksums)
    (BASE / 'data/study_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Packaged {len(items)} originals and {len(items)} Grad-CAM images. Dataset: {version[:12]}')

if __name__ == '__main__':
    prepare()
