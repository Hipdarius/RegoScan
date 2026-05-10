"use client";

import { DocPage, FactGrid, Section } from "@/components/DocPage";

export default function MethodsPage() {
  return (
    <DocPage
      eyebrow="Methods · Models · Calibration"
      title="How the numbers earn their decimal places."
      intro="VERA's headline figure — 99.3 % cross-seed accuracy on synthetic data — is one number among many, none of which mean anything outside the procedure that produced them. This page documents how the data was generated, how the model was trained, and what the uncertainty fields actually mean."
    >
      <Section title="Headline metrics">
        <FactGrid
          items={[
            { label: "Tests passing", value: "214" },
            { label: "Cross-seed acc.", value: "99.3 %", note: "synthetic" },
            { label: "ECE (calibrated)", value: "≤ 1.5 %", note: "15-bin" },
            { label: "Inference (FP32)", value: "< 5 ms", note: "CPU" },
            { label: "Model size", value: "707 KB", note: "INT8 ONNX" },
            { label: "INT8 accuracy drop", value: "0.0 pp", note: "lossless" },
            { label: "SAM baseline", value: "16.8 %", note: "≈ chance for k=6" },
            { label: "CNN improvement", value: "+82.8 pp", note: "over SAM" },
            { label: "Active-learning lift", value: "≈ 2× efficiency", note: "vs. random" },
          ]}
        />
      </Section>

      <Section title="Synthetic data generation">
        <p>
          The dataset is generated procedurally from
          <code> src/vera/synth.py</code>. Endmember spectra come from
          parameterised crystal-field band models (Burns 1993) plus a
          continuum slope, then mixed at random fractions to simulate
          regolith composition. Two mixing models are supported: a
          linear additive baseline and a Hapke (1981) intimate-mixture
          model implemented via the closed-form Inverse Multiple
          Scattering Approximation (IMSA). The Hapke roundtrip
          (<code>r_to_w → mix → w_to_r</code>) is exact to machine
          epsilon.
        </p>
        <p>
          Each measurement augments the mixed spectrum with realistic
          noise: Poisson-like counts on the spectrometer, Gaussian on
          the AS7265x triad, slope-and-bias drift to simulate
          temperature, calibration error on the SWIR pair, and
          fluorescence baseline shift on the LIF. The augmentation
          parameters were chosen by inspecting the first lab spectra
          we have access to, then loosened by ~30 % to leave headroom
          for distribution shift on real samples.
        </p>
      </Section>

      <Section title="Training">
        <p>
          A 1D ResNet on the 321-channel concatenated input, three
          residual stages of (32, 64, 128) channels, stride-2
          downsampling, global average pooling. About 280 K
          parameters. Trained with AdamW at 1e-3, cosine schedule
          over 60 epochs, batch size 128. Two output heads: a
          six-way softmax for class and a sigmoid for the ilmenite
          mass-fraction regression. Class loss is cross-entropy;
          regression is MSE on the logit-transformed fraction. Cross
          validation across five seeds gives a 99.3 ± 0.4 % accuracy
          band; expected calibration error after temperature scaling
          stays below 1.5 % (15-bin estimator).
        </p>
      </Section>

      <Section title="Calibration">
        <p>
          Five corrections are stacked, each implemented in{" "}
          <code>src/vera/calibrate.py</code>:
        </p>
        <ol className="list-decimal space-y-2 pl-6">
          <li>
            <strong>Dark subtraction.</strong> Frame-level dark
            reference subtracted before any other step.
          </li>
          <li>
            <strong>Per-pixel temperature correction.</strong> Each
            pixel's dark current grows linearly with sensor
            temperature; the per-pixel slope is fitted via vectorised
            least squares and applied at inference.
          </li>
          <li>
            <strong>Integration-time normalisation.</strong> Counts
            scale linearly with integration; we divide by exposure to
            get counts/ms, so adaptive integration doesn't change the
            measurement.
          </li>
          <li>
            <strong>White-reference division.</strong> A BaSO₄ white
            puck is captured under the same illumination; reflectance
            is the ratio.
          </li>
          <li>
            <strong>Photometric correction.</strong> Lommel-Seeliger
            is applied for off-normal viewing geometry, with a
            Lambertian fallback for matte calibration targets.
          </li>
        </ol>
        <p>
          A <code>CalibrationProfile</code> dataclass persists the
          dark intercept/slope, white reference, integration time,
          and reference temperature in a single JSON next to the
          model artefacts so deployments don't drift from training.
        </p>
      </Section>

      <Section title="Uncertainty">
        <p>
          <code>src/vera/uncertainty.py</code> exposes four
          quantities: the calibrated posterior, the runner-up margin,
          the normalised entropy, and a four-state status field. The
          status thresholds are fitted on a held-out split rather
          than guessed: <code>likely_ood</code> when normalised
          entropy is above the 95th percentile of in-distribution
          held-out, <code>low_confidence</code> when the top-1
          probability is under a calibrated threshold,{" "}
          <code>borderline</code> when the runner-up is within a
          margin of the top, and <code>nominal</code> otherwise.
        </p>
        <p>
          Temperature scaling minimises NLL on the held-out set via
          1-D grid search over T ∈ [0.5, 5.0]. The fitted T is
          persisted in <code>meta.json</code> so deployments inherit
          calibration. Expected calibration error (ECE) is estimated
          with the 15-bin estimator from Guo et al. 2017.
        </p>
      </Section>

      <Section title="OOD detection">
        <p>
          Two signals feed the OOD detector. The first is a
          calibrated entropy threshold (above): the model says it's
          unsure. The second is SAM/CNN disagreement: if the
          Spectral-Angle-Mapper baseline classifies into a different
          class than the CNN at high confidence, the sample is
          flagged. SAM is essentially chance on the synthetic
          training distribution, so its agreements are uninformative
          but its <em>disagreements</em> reliably indicate
          distribution shift, since SAM uses spectral shape only and
          fails predictably on the wrong shape.
        </p>
      </Section>

      <Section title="Active learning">
        <p>
          With limited real-sample budget, the active learner ranks
          unlabelled candidates by an acquisition score combining
          normalised entropy, top-1 margin, and SAM/CNN disagreement.
          The top-K ranks are returned by{" "}
          <code>src/vera/active_learning.py</code>. On synthetic
          benchmarks the active learner reaches the same accuracy
          target as random sampling with roughly half the labels —
          a ~2× annotation-efficiency gain. The first ten real
          spectra captured will be the highest-ranked synthetic
          candidates, biased toward ambiguous ilmenite/pyroxene
          mixtures where the cost of being wrong is highest.
        </p>
      </Section>

      <Section title="Linear-vs-Hapke ablation">
        <p>
          The mixing-model choice is testable, not assumed. The
          ablation script <code>scripts/ablate_mixing.py</code>
          trains two classifiers — one on linear-mixed synthetic
          data, one on Hapke-mixed — and evaluates each on both
          distributions. The script outputs a 2 × 2 transfer matrix
          plus per-class accuracy. On synthetic-only data the two
          are within noise; the real test is how each transfers to
          pestle-ground laboratory mixtures, which is the next
          milestone once the probe is assembled.
        </p>
      </Section>

      <Section title="Embedded deployment">
        <p>
          The model lives at three quality tiers. FP32 ONNX is the
          canonical artefact and the one served in the demo. INT8
          static quantisation (via{" "}
          <code>onnxruntime.quantization</code>, calibrated on 256
          real training samples) compresses to 707 KB at zero
          accuracy loss — a 3.7× reduction. The TFLite Micro path
          for ESP32 deployment requires a Linux build host; the
          script <code>scripts/build_tflite_micro.sh</code> wraps
          tensorflow + onnx-tf and emits a flatbuffer. INT8 ONNX
          serves as the calibration source so the embedded path
          inherits the same quantisation as the laptop fallback.
        </p>
      </Section>

      <Section title="Reproducibility">
        <p>
          Every artefact in <code>runs/</code> is keyed by a 12-hex
          run hash that includes the dataset seed, the augmentation
          seed, the model hyperparameters, and the calibration
          profile hash. The trainer's <code>meta.json</code> records
          the fully-resolved configuration; loading it back into the
          inference engine fails fast on schema-version mismatch.
          214 tests run on every change, including
          property-based ones for the calibration math.
        </p>
      </Section>
    </DocPage>
  );
}
