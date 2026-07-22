"""VERA — VIS/NIR + SWIR + 405 nm LIF probe for lunar regolith mineralogy.

This package contains the software pipeline only. There is no hardware
code here — measurements are always read from / written to the canonical
CSV schema defined in :mod:`vera.schema`.

Submodule overview
------------------
- :mod:`vera.schema`           Wire format + sensor-mode definitions
- :mod:`vera.synth`            Synthetic-spectrum generator (linear + Hapke)
- :mod:`vera.augment`          Noise injection + augmentation
- :mod:`vera.datasets`         Sample-level splits + PyTorch wrapper
- :mod:`vera.preprocess`       SNV / Savitzky-Golay / ALS baseline
- :mod:`vera.features`         Hand-crafted band-depth features
- :mod:`vera.models.cnn`       1D ResNet classifier + ilmenite head
- :mod:`vera.models.plsr`      PLSR / Random Forest baseline
- :mod:`vera.train`            Trainer entry point
- :mod:`vera.evaluate`         Cross-seed CV, ROC, bootstrap CIs
- :mod:`vera.calibrate`        Dark / white / temp / photometric corrections
- :mod:`vera.uncertainty`      Entropy + margin + four-state OOD classifier
- :mod:`vera.inference`        ONNX Runtime engine for deployment
- :mod:`vera.inference_robust` TTA + sample fusion + temperature scaling
- :mod:`vera.sam`              Spectral Angle Mapper baseline
- :mod:`vera.active_learning`  Pool-based candidate ranker
- :mod:`vera.quantize`         FP32 → INT8 ONNX export
"""

__version__ = "0.1.0"
