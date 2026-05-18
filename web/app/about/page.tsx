"use client";

import {
  Bibliography,
  DocPage,
  Prose,
  Section,
  SpecList,
  VitalStats,
} from "@/components/DocPage";
import { FadeIn, StatusRow } from "@/components/docs/primitives";
import { ProbeSchematic, Roadmap, SplitColumn } from "@/components/docs/about-extras";

// Three groups, in this order: (1) why ISRU and ilmenite, (2) why these
// optical channels, (3) why this model architecture & calibration. Each
// `used` line points at the section of VERA the paper actually informs.
const REFERENCES = [
  {
    authors: "NASA",
    year: "2020",
    title: "Artemis Plan: NASA's Lunar Exploration Program Overview",
    venue: "NASA HQ · NP-2020-05-2853-HQ",
    used: "Why ISRU. Identifying high-FeO/TiO₂ deposits at the south polar region is on the Artemis critical path.",
  },
  {
    authors: "Sanders & Larson",
    year: "2013",
    title: "Progress in Lunar In-Situ Resource Utilization under NASA's ETDP",
    venue: "J. Aerospace Eng. 26 (1) · 5–17",
    used: "Why ilmenite. H₂ reduction at ≈ 900 °C yields water without melting the regolith — the cheapest oxygen route.",
  },
  {
    authors: "Pieters et al.",
    year: "2009",
    title: "The Moon Mineralogy Mapper (M³) on Chandrayaan-1",
    venue: "Current Science 96 (4) · 500–505",
    used: "Why these wavelengths. M³'s 340–2500 nm coverage validates the 1-µm Fe²⁺ band as the diagnostic feature.",
  },
  {
    authors: "Burns",
    year: "1993",
    title: "Mineralogical Applications of Crystal Field Theory",
    venue: "Cambridge University Press · 2nd ed.",
    used: "How mineralogy maps to spectra. Band positions for Fe²⁺ in olivine, pyroxene, ilmenite — the basis of the synthetic endmembers.",
  },
  {
    authors: "Hapke",
    year: "1981",
    title: "Bidirectional Reflectance Spectroscopy I — Theory",
    venue: "JGR 86 (B4) · 3039–3054",
    used: "Why the synthetic mixer is non-linear. IMSA closed form gives a r↔w roundtrip exact to machine ε.",
  },
  {
    authors: "Kruse et al.",
    year: "1993",
    title: "The Spectral Image Processing System (SIPS)",
    venue: "Remote Sens. Environ. 44 · 145–163",
    used: "The SAM baseline. Used as both a paper-grade ablation and an OOD-disagreement signal for the four-state status field.",
  },
  {
    authors: "He et al.",
    year: "2016",
    title: "Deep Residual Learning for Image Recognition",
    venue: "CVPR · arXiv:1512.03385",
    used: "Backbone. The 1D ResNet over the spectral axis — three stride-2 stages, ≈ 280 K parameters total.",
  },
  {
    authors: "Guo et al.",
    year: "2017",
    title: "On Calibration of Modern Neural Networks",
    venue: "ICML · PMLR 70",
    used: "Why the posterior is trustworthy. Temperature scaling + 15-bin ECE — the basis of the ≤ 1.5 % calibrated ECE figure.",
  },
  {
    authors: "Hendrycks & Gimpel",
    year: "2017",
    title: "A Baseline for Detecting OOD Examples in Neural Networks",
    venue: "ICLR · arXiv:1610.02136",
    used: "OOD detection. Calibrated entropy thresholding — the basis of likely_ood in the four-state status field.",
  },
  {
    authors: "Settles",
    year: "2009",
    title: "Active Learning Literature Survey",
    venue: "Univ. Wisconsin–Madison · CS Tech. Report 1648",
    used: "How to spend the real-sample budget. The entropy + margin terms in active_learning.acquisition_score come from this taxonomy.",
  },
  {
    authors: "Lommel & Seeliger",
    year: "1887 / 1924",
    title: "Photometric law for diffuse reflectance",
    venue: "Astronomische Nachrichten",
    used: "Off-normal viewing geometry correction in calibrate.lommel_seeliger.",
  },
];

export default function AboutPage() {
  return (
    <DocPage
      eyebrow="Darius Ferent · Lycée des Arts et Métiers · Luxembourg"
      title="A handheld lunar mineral classifier."
      intro="VERA is a compact dual-sensor probe that classifies lunar regolith mineralogy in real time on a microcontroller. It targets the most actionable ISRU question: where is the ilmenite, the leading candidate for in-situ oxygen extraction."
      aside={<ProbeSchematic />}
      vitals={
        <VitalStats
          items={[
            { label: "Form", value: "Handheld" },
            { label: "BOM", value: "≈ €658" },
            { label: "Inference", value: "< 5 ms · CPU" },
            { label: "Tests", value: "214 / 214" },
            { label: "TRL", value: "3 hw · 5 sw" },
            { label: "License", value: "MIT" },
          ]}
        />
      }
    >
      <Section number="01" title="Why this exists">
        <Prose>
          <p>
            Lunar In-Situ Resource Utilization depends on knowing what
            minerals are beneath the regolith. Oxygen extraction from
            ilmenite — <code>FeTiO₃</code> — is the most credible near-term
            ISRU pathway, but the tools that can answer "is there ilmenite
            here" are either too heavy, too slow, or require sample
            return.
          </p>
          <p>
            VERA targets a handheld instrument class. Hydrogen reduction at
            ≈ 900 °C releases water from ilmenite; electrolysis yields
            breathing oxygen and hydrogen feedstock. Ilmenite is abundant
            in lunar mare basalts and stable enough to survive impact
            gardening — a uniquely tractable target if you can find it.
          </p>
          <p>
            The probe scans a surface in seconds and emits a calibrated
            mineral classification plus a continuous ilmenite mass-fraction
            estimate. Inference is under 5 ms on CPU; the full uncertainty
            tuple (posterior, margin, normalised entropy, four-state
            status) ships with every prediction so the reader can decide
            what to trust.
          </p>
        </Prose>
      </Section>

      <Section number="02" title="The four optical channels">
        <Prose>
          <p>
            Four channels arranged around one sample window: a 288-channel
            VIS/NIR spectrometer, an 18-band multispectral triad, a
            two-band InGaAs SWIR pair targeting the 1-µm Fe²⁺ band, and a
            405 nm laser for fluorescence on plagioclase. Twelve narrowband
            LEDs around the rim do the illumination.
          </p>
          <p>
            Each channel is chosen to resolve a band the others cannot:
            NIR for Fe²⁺ crystal-field, SWIR for the 1-µm tail, AS7265x for
            continuum coverage, LIF for plagioclase fluorescence. The
            321-channel feature vector is the same in firmware, in
            training, and in the ONNX inference engine — one schema, one
            source of truth.
          </p>
        </Prose>
      </Section>

      <Section number="03" title="What's real, what's pending">
        <Prose>
          <p>
            The software stack is built and tested. The hardware stack is
            specified, sourced, and waiting on assembly. When validation
            is pending, the interface says so.
          </p>
        </Prose>
        <FadeIn>
          <SplitColumn
            leftLabel="Real · shipped"
            leftTitle="software stack"
            rightLabel="Pending · roadmap"
            rightTitle="hardware stack"
            left={
              <ul>
                <StatusRow state="ok" label="Synthetic data generator (linear + Hapke IMSA)" status="DONE" />
                <StatusRow state="ok" label="1D ResNet trained · 99.3 % cross-seed accuracy" status="DONE" />
                <StatusRow state="ok" label="ONNX export + INT8 lossless quantization · 707 KB" status="DONE" />
                <StatusRow state="ok" label="Calibration pipeline · 5 stages · persisted" status="DONE" />
                <StatusRow state="ok" label="Uncertainty + 4-state classifier · ECE ≤ 1.5 %" status="DONE" />
                <StatusRow state="ok" label="OOD detector · SAM/CNN disagreement signal" status="DONE" />
                <StatusRow state="ok" label="Active learning · ≈ 2× annotation efficiency" status="DONE" />
                <StatusRow state="ok" label="FastAPI service + Next.js console · 214 tests" status="DONE" />
              </ul>
            }
            right={
              <ul>
                <StatusRow state="pending" label="Probe assembly (C12880MA + AS7265x + SWIR)" status="NEXT" />
                <StatusRow state="pending" label="12-LED narrowband illumination array" status="NEXT" />
                <StatusRow state="pending" label="BaSO₄ white reference + endmember capture" status="NEXT" />
                <StatusRow state="pending" label="Real-spectra dataset (zero collected)" status="NEXT" />
                <StatusRow state="pending" label="Real-sample temperature scaling refit" status="LATER" />
                <StatusRow state="pending" label="TFLite Micro flash to ESP32-S3 on Linux" status="LATER" />
                <StatusRow state="pending" label="Live demo with assembled probe" status="LATER" />
                <StatusRow state="pending" label="Validation against XRF at LIST" status="LATER" />
              </ul>
            }
          />
        </FadeIn>
      </Section>

      <Section number="04" title="Mission roadmap">
        <Prose>
          <p>
            Ten milestones across the project. The first five are the
            software foundation; everything from M5 onward depends on
            assembling the physical probe.
          </p>
        </Prose>
        <FadeIn>
          <Roadmap />
        </FadeIn>
      </Section>

      <Section number="05" title="Standing on the shoulders of">
        <Prose>
          <p>
            Eleven papers underpin the design choices, grouped by what they
            justify: why ISRU and ilmenite, why these optical channels, and
            why this model architecture and calibration. Each entry's →
            line names the part of VERA that depends on it. Full
            annotations and a few additional references live in{" "}
            <code>docs/paper-notes.md</code>; commits in this repo carry
            paper-section impact tags so the eventual writeup can pull
            from the engineering journal directly.
          </p>
        </Prose>
        <FadeIn>
          <Bibliography
            note="Why ISRU · why these channels · why this model"
            items={REFERENCES}
          />
        </FadeIn>
      </Section>

      <Section number="06" title="Provenance">
        <Prose>
          <p>
            Every figure on this site is reproducible from{" "}
            <code>runs/&lt;run-hash&gt;/meta.json</code>. The model
            identifier, schema version, and calibration profile hash are
            persisted next to the ONNX artefact and validated on load.
          </p>
        </Prose>
        <SpecList
          size="footnote"
          items={[
            { label: "Builder", value: "Darius Ferent · Lycée des Arts et Métiers · LU" },
            { label: "Competition", value: "Jonk Fuerscher 2027 · Luxembourg" },
            { label: "License", value: "MIT · github.com/Hipdarius/VERA" },
            { label: "Schema", value: "v1.2.0 · firmware ↔ bridge ↔ API ↔ console" },
            { label: "Inference", value: "ONNX Runtime · FP32 canonical · INT8 deployable" },
            { label: "Tests", value: "214 passing · property + unit · pytest + tsc + PlatformIO" },
          ]}
        />
      </Section>
    </DocPage>
  );
}
