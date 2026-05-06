"use client";

import { DocPage, FactGrid, Section } from "@/components/DocPage";

export default function AboutPage() {
  return (
    <DocPage
      eyebrow="About · Mission · Provenance"
      title="A handheld lunar mineral classifier."
      intro="VERA — Visible & Emission Regolith Assessment — is a compact dual-sensor probe that classifies lunar regolith mineralogy in real time on a microcontroller. It targets the most actionable ISRU question: where is ilmenite, the leading candidate for in-situ oxygen extraction."
    >
      <Section title="Why this exists">
        <p>
          Lunar In-Situ Resource Utilization (ISRU) depends on knowing
          <em> what minerals are beneath the regolith</em>. Oxygen
          extraction from ilmenite (FeTiO₃) is the most credible
          near-term ISRU pathway, but the existing prospecting tools
          are either too heavy, too slow, or require sample return.
          VERA targets a handheld instrument class that can scan a
          surface in seconds and emit a calibrated mineral classification
          plus a continuous ilmenite mass-fraction estimate.
        </p>
        <p>
          The probe combines three sensing modalities — a 288-channel
          VIS/NIR spectrometer, a dedicated SWIR photodiode pair at
          940/1050 nm targeting the 1-µm Fe²⁺ crystal-field band, and a
          405 nm laser-induced fluorescence channel — into a single
          measurement processed by a 1D ResNet under 5 ms on CPU.
        </p>
      </Section>

      <Section title="At a glance">
        <FactGrid
          items={[
            { label: "Builder", value: "Darius Ferent" },
            { label: "Institution", value: "Lycée des Arts et Métiers, Luxembourg" },
            { label: "Competition", value: "Jonk Fuerscher 2027" },
            { label: "Mineral classes", value: "6", note: "incl. mixed regolith" },
            { label: "Sensor channels", value: "321", note: "combined mode" },
            { label: "Cross-seed accuracy", value: "99.3 %", note: "synthetic" },
            { label: "Tests", value: "214 passing" },
            { label: "Inference time", value: "< 5 ms", note: "CPU FP32" },
            { label: "Schema", value: "v1.2.0" },
          ]}
        />
      </Section>

      <Section title="What's real, what's pending">
        <p>
          Software is end-to-end functional: synthetic data generation,
          training, ONNX export with lossless INT8 quantization,
          calibration pipeline, uncertainty quantification, an OOD
          detector, a SAM baseline, and an active-learning loop. 214
          tests pass.
        </p>
        <p>
          Hardware is BOM-defined but not yet assembled. The firmware
          state machine is wired through to the SWIR acquisition and
          adaptive integration time, ready to drive real components.
          The competition probe needs the C12880MA spectrometer, the
          AS7265x triad, the InGaAs SWIR photodiode through an ADS1115
          ADC, and a 12-LED narrowband illumination array.
        </p>
        <p>
          Real spectra: zero collected. The 99.3% cross-seed accuracy
          is on synthetic data only. The next milestone is capturing
          BaSO₄ white reference plus reference minerals (olivine,
          pyroxene, anorthite, ilmenite, obsidian) with the assembled
          probe and fitting the temperature-scaling calibration on
          that real distribution.
        </p>
      </Section>

      <Section title="Standing on the shoulders of">
        <p>
          The instrument design borrows from M³ (Moon Mineralogy
          Mapper, Pieters et al. 2009) for spectral coverage choices
          and from the Hapke (1981) intimate-mixture theory for the
          synthetic-data mixing model. Crystal-field band placement
          follows Burns (1993). Photometric correction uses
          Lommel-Seeliger. The classifier architecture is a 1D ResNet
          (He et al. 2016) adapted to 1D spectral input, with the
          uncertainty calibration following Guo et al. (2017).
        </p>
        <p>
          The full bibliography sits in <code>docs/paper-notes.md</code>
          with paper-section impact tags on every commit so the
          eventual 15–20 page LaTeX writeup can pull from the
          engineering journal directly.
        </p>
      </Section>
    </DocPage>
  );
}
