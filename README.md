<div align="center">

# Hook-Gen

**Turn any drum loop into five melodic hooks that lock to the groove.**

[![CI](https://github.com/cwklurks/hook-gen/actions/workflows/test.yml/badge.svg)](https://github.com/cwklurks/hook-gen/actions/workflows/test.yml)

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178c6.svg)](https://www.typescriptlang.org/)

[View Demo](https://hook-gen-nine.vercel.app/) • [Report Bug](https://github.com/cwklurks/hook-gen/issues) • [Request Feature](https://github.com/cwklurks/hook-gen/issues)

</div>

---

## 📖 About

**Hook-Gen** is a musical ideation engine designed for beatmakers and developers. Unlike "black box" generative AI that relies on massive pre-trained checkpoints, Hook-Gen uses **deterministic, explainable algorithms** to analyze audio and generate musical content.

Drop in a rhythmic loop (WAV/MP3), and the system analyzes the **onset histogram** (groove) and **chroma features** (key/scale). It then procedurally generates monophonic MIDI/Audio hooks that mathematically lock to your loop's specific feel.

### Key Features

* **🎛️ Groove-Aware Sampling:** Rhythm generation is driven by the uploaded loop's onset density.

* **🎯 Contextual Pitching:** Automatic scale detection using `librosa` chroma templates.

* **🎹 In-Browser Synthesis:** Instant preview using Tone.js on the frontend.

* **📦 Production Ready:** Downloads organized zip bundles with WAV/MIDI stems.

* **⚡ Lightweight:** Runs entirely on CPU; no GPU required.

---

## 📸 Demo

![Application Demo](docs/demo.gif)

---

## 🛠 Tech Stack

This project uses a modern decoupled architecture:

### **Frontend (The Interface)**

* **Framework:** [Next.js 14](https://nextjs.org/) (React Server Components)

* **Styling:** Tailwind CSS + Framer Motion

* **Audio:** [Wavesurfer.js](https://wavesurfer-js.org/) (Visualization) + [Tone.js](https://tonejs.github.io/) (Playback)

### **Backend (The Brain)**

* **API:** [FastAPI](https://fastapi.tiangolo.com/) (Python)

* **DSP:** [Librosa](https://librosa.org/) (Audio Analysis) + NumPy

* **MIDI:** Mido / PrettyMIDI

---

## 🚀 Quick Start

The easiest way to run Hook-Gen locally is via Docker.

### Prerequisites

* Docker & Docker Compose

### Installation

1.  **Clone the repo**

    ```bash

    git clone https://github.com/cwklurks/hook-gen.git

    cd hook-gen

    ```

2.  **Start the services**

    ```bash

    docker-compose up --build

    ```

3.  **Access the app**

    * Frontend: `http://localhost:3000`

    * Backend API Docs: `http://localhost:8000/docs`

---

## 🧠 How It Works (The Algorithm)

Hook-Gen operates on an "Explainable AI" philosophy. Here is the pipeline:

1.  **Signal Conditioning:** The audio is loaded into `Librosa`, converted to mono, and trimmed.

2.  **Rhythm Extraction:**

    * We calculate an onset envelope to estimate BPM.

    * A 16-step **Groove Histogram** is built by mapping detected onsets to a 16th-note grid.

3.  **Scale Detection:**

    * We generate a Chroma Constant-Q Transform (CQT).

    * This vector is compared against 24 template scales (Major/Minor for all roots) to determine the musical key confidence.

4.  **Generation:**

    * **Rhythm:** We sample from the Groove Histogram (weighted by the "Groove Push" slider).

    * **Pitch:** We perform a constrained random walk within the detected scale, ensuring the phrase resolves to the tonic (root note).

---

## 📂 Project Structure

```bash

hook-gen/

├── backend/                # Python FastAPI Server

│   ├── app/

│   │   ├── motif.py        # Pitch generation logic

│   │   ├── rhythm.py       # Tempo & Groove analysis

│   │   └── export.py       # MIDI/WAV file creation

│   └── examples/           # Included audio loops for testing

│

├── frontend/               # Next.js Application

│   ├── src/components/     # React UI Components (PianoRoll, Waveform)

│   └── public/             # Static assets

│

└── hook-aid/               # Legacy Streamlit Prototype (Reference)

```

---

## 🤝 Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are greatly appreciated.

1. Fork the Project

2. Create your Feature Branch (git checkout -b feature/AmazingFeature)

3. Commit your Changes (git commit -m 'Add some AmazingFeature')

4. Push to the Branch (git push origin feature/AmazingFeature)

5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See LICENSE for more information.

---

## 🔮 Roadmap

- [ ] MIDI Export UI: Allow downloading .mid files directly from the player.

- [ ] Polyphony: Add chord generation based on implied harmony.

- [ ] Style Presets: Add "Trap", "House", and "Lofi" bias settings to the rhythm sampler.

---

<div align="center"> <small>Built with 🎵 by <a href="https://github.com/cwklurks">cwklurks</a></small> </div>
