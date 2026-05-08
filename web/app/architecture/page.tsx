"use client";

import { DocPage, FactGrid, Section } from "@/components/DocPage";

export default function ArchitecturePage() {
  return (
    <DocPage
      eyebrow="Architecture · Stack · Data flow"
      title="From photons to a class label, in five layers."
      intro="VERA is a vertical stack: optical front end → 32-bit MCU → USB-CDC bridge → FastAPI inference service → Next.js console. The same JSON schema flows from the firmware to the browser. Versioned at v1.2.0; every layer rejects mismatched payloads."
    >
      <Section title="Stack at a glance">
        <FactGrid
          items={[
            { label: "Front end", value: "C12880MA + AS7265x", note: "VIS/NIR + triad" },
            { label: "SWIR", value: "InGaAs PD + ADS1115", note: "16-bit ADC" },
            { label: "Illumination", value: "12 narrowband LEDs + 405 nm laser", note: "365–1050 nm" },
            { label: "MCU", value: "ESP32-S3", note: "240 MHz, 512 KB SRAM" },
            { label: "Bridge", value: "USB-CDC", note: "JSON line protocol" },
            { label: "Inference", value: "FastAPI + ONNX Runtime", note: "Python 3.12" },
            { label: "Console", value: "Next.js 14 + React 18", note: "App Router" },
            { label: "Schema", value: "v1.2.0", note: "shared TS + py" },
            { label: "Firmware tests", value: "platformio native", note: "host-side" },
          ]}
        />
      </Section>

      <Section title="Optical front end">
        <p>
          The Hamamatsu C12880MA delivers 288 channels from 340–850 nm
          in a 20 × 12 × 10 mm footprint — small enough for a handheld
          probe, sensitive enough for direct reflectance work without
          a cooled sensor. Sequential readout is driven by an
          ESP32-controlled clock; integration time is rescaled
          adaptively from frame to frame so the 95th-percentile pixel
          targets ~50% of the ADC range. The AS7265x triad fills the
          spectral gaps with 18 wider channels; the InGaAs photodiode
          on an ADS1115 16-bit ADC samples at 940 nm and 1050 nm to
          reach into the SWIR where the 1-µm Fe²⁺ band is strongest.
        </p>
        <p>
          A 405 nm laser diode adds a fluorescence channel. Plagioclase
          (anorthite) emits in the blue under UV-violet excitation —
          a property that crystal-field theory does not capture from
          reflectance alone, so the LIF channel adds genuinely new
          information rather than just re-encoding the spectrum.
        </p>
      </Section>

      <Section title="MCU firmware">
        <p>
          The firmware runs a finite-state machine on the ESP32-S3
          loop: <code>IDLE → DARK → ACQUIRE_VIS → ACQUIRE_AS7 →
          ACQUIRE_SWIR → ACQUIRE_LIF → EMIT → IDLE</code>. Each state
          is non-blocking — the loop polls a state's <code>step()</code>
          method, which advances when its hardware is ready.
        </p>
        <p>
          SWIR acquisition itself runs a sub-state machine:
          <code> DARK_REF → LED_940_ON → SETTLE_940 → READ_940 →
          LED_OFF → LED_1050_ON → SETTLE_1050 → READ_1050 → DONE</code>.
          Each LED gets a 5 ms settle window before N=8 ADS1115 reads
          are averaged — the dark-subtracted result is the SWIR sample.
          No <code>delay()</code> calls; the loop stays at ~1 kHz so
          telemetry remains responsive under acquisition.
        </p>
        <p>
          Adaptive integration uses a counting-sort histogram (4096
          bins, no heap) to find the 95th-percentile pixel value in
          O(N + 4096). The next integration time is rescaled toward
          half-range; the controller is rate-limited by a single
          smoothing factor to avoid oscillation under changing scenes.
        </p>
      </Section>

      <Section title="Wire protocol">
        <p>
          The MCU emits one JSON object per frame over USB-CDC,
          newline-delimited. Schema v1.2.0:
        </p>
        <pre className="overflow-x-auto rounded border border-slate-700 bg-slate-900/60 p-3 text-[11px] leading-relaxed">{`{
  "schema": "1.2.0",
  "ts_ms": 1745654321,
  "spec": [<288 floats, 0..1>],
  "as7":  [<18 floats, 0..1>]?,
  "swir": [<2 floats, 0..1>]?,
  "led":  [<12 floats, 0..1>],
  "lif":  <float, 0..1>,
  "temp_c": <float>,
  "integ_us": <int>
}`}</pre>
        <p>
          The bridge validates length, range, and schema version on
          every frame. Mismatched frames are dropped with a logged
          counter; valid frames are written to a CSV stream and
          forwarded to the inference API with the canonical feature
          ordering <code>[spec | as7? | swir? | led | lif]</code>. The
          same ordering is used in training, so there is exactly one
          source of truth for feature layout.
        </p>
      </Section>

      <Section title="Inference service">
        <p>
          FastAPI exposes <code>/api/health</code>,{" "}
          <code>/api/predict</code>, and <code>/api/predict/demo</code>.
          ONNX Runtime hosts the trained 1D ResNet — FP32 by default,
          INT8 for embedded deployment. Predictions return the full
          uncertainty tuple: posterior over six classes, the runner-up
          margin, normalised entropy, and a four-state status field
          (<code>nominal</code> / <code>borderline</code> /{" "}
          <code>low_confidence</code> / <code>likely_ood</code>).
          Temperature scaling is applied post-softmax; the temperature
          is fitted on a held-out split and persisted in{" "}
          <code>meta.json</code>.
        </p>
        <p>
          The OOD detector trips when entropy exceeds a calibrated
          threshold or when the SAM and CNN disagree at confidence
          ≥ 0.5. SAM acts as a free second opinion — its baseline
          accuracy on synthetic spec-only is essentially chance (16.8%
          on six classes), but its disagreements with the CNN are a
          reliable distribution-shift signal.
        </p>
      </Section>

      <Section title="Console">
        <p>
          The Next.js app reads from the FastAPI service and renders
          the spectrum, the ilmenite mass-fraction gauge, the class
          posterior, and a scrolling mission log. The aesthetic is
          oscilloscope-style: monospace numerics, hairline borders,
          a single accent cyan, dark mode by default. The console
          deliberately avoids glassmorphism, gradients, and any
          decorative effect that would obscure the data.
        </p>
        <p>
          The same console hosts this About / Architecture / Methods
          documentation so the project reads as a single instrument
          rather than a marketing site separated from the tool.
        </p>
      </Section>
    </DocPage>
  );
}
