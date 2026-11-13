"""Train and evaluate the Dhawani complaint classifiers. Run: python -m ml.train"""
import json, joblib
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from ml.data import build

OUT = Path(__file__).parent / "model"


def pipe():
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, lowercase=True),
        LogisticRegression(C=20, max_iter=2000, class_weight="balanced"))


def main():
    rows = build()
    X = [r[0] for r in rows]
    y_cat = np.array([r[1] for r in rows])
    y_urg = np.array([r[2] for r in rows])
    groups = np.array([r[3] for r in rows])
    cv = GroupKFold(n_splits=5)  # whole base phrases are held out, so test phrases are unseen
    report = {"samples": len(rows)}
    for name, y in [("category", y_cat), ("urgency", y_urg)]:
        pred = cross_val_predict(pipe(), X, y, groups=groups, cv=cv)
        report[name] = {"cv_accuracy": round(float(accuracy_score(y, pred)), 3)}
        print(f"\n== {name} (5-fold, unseen phrases) ==")
        print(classification_report(y, pred, digits=3))
    OUT.mkdir(exist_ok=True)
    joblib.dump({"category": pipe().fit(X, y_cat), "urgency": pipe().fit(X, y_urg)}, OUT / "dhawani.joblib")
    (OUT / "metrics.json").write_text(json.dumps(report, indent=2))
    print("saved", OUT / "dhawani.joblib", report)


if __name__ == "__main__":
    main()
