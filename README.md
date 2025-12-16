# Maisa Clinical Data Parser

> [!NOTE]
> 🇫🇮 **Suomenkielinen ohjeistus**: [Lue ohjeet suomeksi tästä](README_fi.md)


A Python tool to parse and consolidate HL7 CDA (Clinical Document Architecture) XML files exported from the **Maisa** patient portal (used by **Apotti** in Finland). 

It extracts key health information into a structured, machine-readable JSON format (`patient_history.json`), optimized for further analysis or AI processing.

## 🚀 Features

- **Consolidated Patient History**: Merges data from multiple `DOC*.XML` files into a single chronological timeline.
- **Narrative Extraction**: Intelligently extracts free-text clinical notes ("Päivittäismerkinnät", "Hoidon tarpeen arviointi") while filtering out redundant structured lists (medications, labs) to reduce noise.
- **Structured Data Parsing**:
  - **Patient Profile**: Demographics, contact info.
  - **Medications**: Active list and history with dates and dosage.
  - **Lab Results**: test names, values, units, and timestamps.
  - **Diagnoses**: Active problems and ICD-10 codes.
  - **Allergies**: Status and substances.
- **Deduplication**: Handles duplicate entries across multiple documents.
- **Clean Output**: Produces a clean `patient_history.json` file.

## 🛠️ Prerequisites

- Python 3.8 or higher
- `pip` (Python package installer)

## 📦 Installation

1.  Clone this repository or download the script.
2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

    *(The primary dependency is `lxml` for efficient XML parsing)*

## 📖 Usage

1.  **Export Data**: Download your health data dump from Maisa ("Tilanneyhteenveto" or similar export). After extracting the ZIP file, you'll see a folder structure like this:

    ```
    Tilanneyhteenveto_DD_Month_YYYY/
    ├── HTML/
    │   ├── IMAGES/
    │   └── STYLE/
    ├── IHE_XDM/
    │   └── <PatientFolder>/     ← This folder contains the XML files!
    │       ├── DOC0001.XML
    │       ├── DOC0002.XML
    │       ├── ...
    │       ├── METADATA.XML
    │       └── STYLE.XSL
    ├── INDEX.HTM
    └── README - Open for Instructions.TXT
    ```

    > [!IMPORTANT]
    > Point the parser to the **`IHE_XDM/<PatientFolder>/`** directory that contains the `DOC*.XML` files, **not** the root extracted folder.

2.  **Run the Parser**:

    ```bash
    python src/maisa_parser.py /path/to/IHE_XDM/<PatientFolder>/
    ```

    For example:
    ```bash
    python src/maisa_parser.py ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/Ilias1/
    ```

    If you run the script from inside the data folder, you don't need arguments:

    ```bash
    cd ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/Ilias1/
    python /path/to/maisa-parser/src/maisa_parser.py
    ```

3.  **View Output**: The script generates a `patient_history.json` file in your current working directory.

## 📂 Output Structure

The generated JSON contains:

```json
{
  "patient_profile": { ... },
  "clinical_summary": {
    "allergies": [ ... ],
    "active_medications": [ ... ],
    "medication_history": [ ... ]
  },
  "lab_results": [ ... ],
  "diagnoses": [ ... ],
  "encounters": [
    {
      "date": "2024-10-10T12:00:00",
      "type": "Hoito- ja palveluyhteenveto",
      "provider": "Dr. Name",
      "notes": "Narrative text of the visit...",
      "source_file": "DOC0018.XML"
    },
    ...
  ]
}
```

## ⚠️ Important Note on Privacy

This tool processes **sensitive personal health information**. 
- **Do not commit** your XML data files or the generated JSON output to GitHub or any public repository.
- A `.gitignore` file is included to help prevent accidental commits of `.XML` and `.json` files.
- Always handle your medical data with care.

## 📥 How to export your data from Maisa

1.  Log in to **[Maisa.fi](https://www.maisa.fi)**.
2.  Go to **Menu** > **Sharing** > **Download My Record** (Lataa tietoni).
3.  Select **"Lucy XML"** (or "Everything").
4.  Download the ZIP file and unzip it.
5.  You will see a folder `IHE_XDM` containing the `DOC*.XML` files. This is the folder you process.

## ⚠️ Legal & Liability Disclaimer

**Disclaimer:** This software is for **educational and informational purposes only**. It is **not** a medical device and should not be used for diagnosis or treatment. Always consult a professional for medical advice. The authors are not responsible for any errors in parsing or data representation.

By using this tool, you agree that you are solely responsible for safeguarding your own medical data.

## 🤝 Contributing

Feel free to submit issues or pull requests if you find bugs or want to improve the parsing logic for different types of Maisa documents.
