"use client";

import {
  DocPage,
  MarginNav,
  Prose,
  Section,
  SpecList,
} from "@/components/DocPage";
import { FadeIn } from "@/components/docs/primitives";
import {
  LayerStack,
  PacketFrame,
  StateMachine,
  WavelengthCoverage,
} from "@/components/docs/diagrams";

const NAV = [
  { number: "01", label: "Stack" },
  { number: "02", label: "Optical" },
  { number: "03", label: "Firmware" },
  { number: "04", label: "Wire" },
  { number: "05", label: "Inference" },
  { number: "06", label: "Console" },
];

export default function ArchitecturePage() {
  return (
    <DocPage
      eyebrow="Architecture · Stack · Data flow"
      title="Five layers, one schema, photons to a label."
      intro="Optical front end → 32-bit MCU → USB-CDC bridge → FastAPI inference → Next.js console. The same JSON schema flows from the firmware to the browser. Versioned at v1.2.0; every layer rejects mismatched payloads."
      marginNav={<MarginNav items={NAV} />}
    >
      <Section number="01" title="The stack at a glance">
        <Prose>
          <p>
            Each layer has one job and one output. Layers above consume the
            layer below over a versioned interface; mismatched schema
            versions fail fast at the boundary rather than corrupting the
            class label silently.
          </p>
        </Prose>
        <FadeIn>
          <LayerStack />
        </FadeIn>
      </Section>

      <Section number="02" title="L1 · Optical front end">
        <Prose>
          <p>
            The Hamamatsu C12880MA delivers 288 channels from 340 – 850 nm
            in a 20 × 12 × 10 mm footprint — small enough for a handheld
            probe, sensitive enough for direct reflectance work without a
            cooled sensor. Integration time rescales adaptively from frame
            to frame so the 95th-percentile pixel targets ≈ 50 % of the
            ADC range.
          </p>
          <p>
            The AS7265x triad fills the spectral gaps with 18 wider
            channels; the InGaAs photodiode on a 16-bit ADC samples 940 nm
            and 1050 nm to reach the 1-µm Fe²⁺ band. A 405 nm laser adds a
            fluorescence channel — plagioclase emits in the blue under
            UV-violet excitation, a property crystal-field theory does not
            capture from reflectance alone. Each channel is chosen to
            resolve a band the others cannot: the fusion is
            information-bearing, not redundant.
          </p>
        </Prose>
        <FadeIn>
          <WavelengthCoverage />
        </FadeIn>
      </Section>

      <Section number="03" title="L2 · MCU firmware">
        <Prose>
          <p>
            The firmware runs a non-blocking finite-state machine on the
            ESP32-S3. Each state's <code>step()</code> advances when its
            hardware is ready; no <code>delay()</code> calls — the loop
            stays at ≈ 1 kHz so telemetry remains responsive under
            acquisition. All buffers are <code>constexpr</code>; there is
            no heap.
          </p>
          <p>
            The exposure controller targets the 95th-percentile pixel at
            ≈ 50 % of full-scale via a counting-sort histogram in
            O(N + 4096) with zero allocation. Each SWIR LED gets a 5 ms
            settle window before N = 8 averaged ADS1115 samples. The
            firmware emits one frame only after both 940 nm and 1050 nm
            cycles have completed.
          </p>
        </Prose>
        <FadeIn>
          <StateMachine
            title="Main loop · 1 kHz"
            loopLabel="loops back to IDLE"
            states={[
              "IDLE",
              "DARK",
              "ACQUIRE_VIS",
              "ACQUIRE_AS7",
              "ACQUIRE_SWIR",
              "ACQUIRE_LIF",
              "EMIT",
            ]}
          />
        </FadeIn>
        <FadeIn delay={0.1}>
          <StateMachine
            title="SWIR sub-state · per ACQUIRE_SWIR entry"
            loopLabel="dark-subtracted result emitted"
            states={[
              "DARK_REF",
              "LED_940_ON",
              "SETTLE_940",
              "READ_940",
              "LED_OFF",
              "LED_1050_ON",
              "SETTLE_1050",
              "READ_1050",
            ]}
          />
        </FadeIn>
      </Section>

      <Section number="04" title="L3 · Wire protocol">
        <Prose>
          <p>
            The MCU emits one JSON object per frame over USB-CDC,
            newline-delimited. The bridge validates length, range, and
            schema version on every frame; mismatched frames are dropped
            with a logged counter. Valid frames flow on in canonical
            feature order <code>[spec | as7? | swir? | led | lif]</code> —
            the same order used in training. Feature layout has exactly
            one source of truth.
          </p>
        </Prose>
        <FadeIn>
          <PacketFrame
            schema="1.2.0"
            fields={[
              { key: "schema",   type: "string",  size: "5 B",  desc: "Wire-format version · rejects on mismatch" },
              { key: "ts_ms",    type: "uint32",  size: "4 B",  desc: "MCU monotonic timestamp · ms since boot" },
              { key: "spec",     type: "float[]", size: "288",  desc: "C12880MA reflectance · normalized 0…1" },
              { key: "as7",      type: "float[]", size: "18",   desc: "AS7265x triad · multispectral mode", optional: true },
              { key: "swir",     type: "float[]", size: "2",    desc: "InGaAs at 940 nm + 1050 nm",          optional: true },
              { key: "led",      type: "float[]", size: "12",   desc: "Per-LED duty · illumination state" },
              { key: "lif",      type: "float",   size: "4 B",  desc: "405 nm fluorescence · normalized 0…1" },
              { key: "temp_c",   type: "float",   size: "4 B",  desc: "Sensor temperature · used for dark current" },
              { key: "integ_us", type: "uint32",  size: "4 B",  desc: "Adaptive integration time · current frame" },
            ]}
          />
        </FadeIn>
      </Section>

      <Section number="05" title="L4 · Inference service">
        <Prose>
          <p>
            FastAPI exposes <code>/api/health</code>,{" "}
            <code>/api/predict</code>, and <code>/api/predict/demo</code>.
            ONNX Runtime hosts the trained 1D ResNet — FP32 by default,
            INT8 for embedded deployment. Predictions return the full
            uncertainty tuple: posterior over six classes, runner-up
            margin, normalised entropy, and a four-state status field.
          </p>
          <p>
            Temperature scaling is applied post-softmax; the temperature
            is fitted on a held-out split and persisted in{" "}
            <code>meta.json</code> next to the ONNX SHA-256, schema
            version, and calibration profile hash. Loading the model
            fails fast on schema-version mismatch. The OOD detector trips
            on calibrated entropy over the 95th percentile or on
            SAM / CNN disagreement at confidence ≥ 0.5.
          </p>
        </Prose>
        <SpecList
          items={[
            { label: "Endpoints", value: "3 · health · predict · demo" },
            { label: "Runtime", value: "ONNX Runtime · Python 3.12 · FastAPI" },
            { label: "Latency p50", value: "< 5 ms · CPU · FP32" },
            { label: "Posterior", value: "6 classes · softmax · temperature-scaled" },
            { label: "Status field", value: "nominal · borderline · low_confidence · likely_ood" },
            { label: "OOD signal", value: "calibrated entropy ∪ SAM/CNN disagreement" },
          ]}
        />
      </Section>

      <Section number="06" title="L5 · Console">
        <Prose>
          <p>
            The Next.js app reads from the FastAPI service and renders
            the spectrum, the ilmenite mass-fraction gauge, the class
            posterior, and a scrolling mission log. The aesthetic is
            oscilloscope-style: monospace numerics, hairline borders, a
            single accent cyan, dark mode by default. The console hosts
            this documentation in the same shell — the project reads as
            one instrument document, not a marketing site separated from
            the tool it describes.
          </p>
          <p>
            Every pixel carries information. Decoration is a tell for
            uncertainty. Numbers are first-class citizens — mono,
            tabular, with explicit units. Color never carries state on
            its own; it is always paired with a textual code (
            <code>NOMINAL</code>, <code>OFFLINE</code>,{" "}
            <code>ERR:42</code>).
          </p>
        </Prose>
      </Section>
    </DocPage>
  );
}
