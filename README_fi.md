# Maisa Clinical Data Parser

Python-työkalu, joka jäsentää ja yhdistää HL7 CDA (Clinical Document Architecture) XML -tiedostoja, jotka on viety **Maisa**-asiakasportaalista (**Apotti**-järjestelmän käytössä Suomessa).

Se poimii keskeiset terveystiedot rakenteiseen, koneluettavaan JSON-muotoon (`patient_history.json`), joka on optimoitu jatkoanalyysiä tai tekoälykäsittelyä varten.

## 🚀 Ominaisuudet

- **Yhdistetty Potilashistoria**: Yhdistää tiedot useista `DOC*.XML`-tiedostoista yhdeksi kronologiseksi aikajanaksi.
- **Tekstimuotoinen Poiminta**: Poimii älykkäästi vapaamuotoiset kliiniset merkinnät ("Päivittäismerkinnät", "Hoidon tarpeen arviointi") ja suodattaa pois toistuvat rakenteiset listat (lääkitys, laboratoriotulokset) vähentääkseen kohinaa.
- **Rakenteisen Tiedon Jäsentäminen**:
  - **Potilasprofiili**: Henkilötiedot, yhteystiedot.
  - **Lääkitys**: Voimassa oleva lääkelista ja historia päivämäärineen ja annostuksineen.
  - **Laboratoriotulokset**: Testien nimet, arvot, yksiköt ja aikaleimat.
  - **Diagnoosit**: Aktiiviset ongelmat ja ICD-10-koodit.
  - **Allergiat**: Tila ja aineet.
- **Kopioiden Poisto**: Käsittelee päällekkäiset merkinnät useista dokumenteista.
- **Puhdas Tuloste**: Tuottaa siistin `patient_history.json`-tiedoston.

## 🛠️ Esivaatimukset

- Python 3.8 tai uudempi
- `pip` (Python-pakettien asentaja)

## 📦 Asennus

1.  Kloonaa tämä repositorio tai lataa skripti.
2.  Asenna tarvittavat riippuvuudet:

    ```bash
    pip install -r requirements.txt
    ```

    *(Pääasiallinen riippuvuus on `lxml` tehokasta XML-jäsennystä varten)*

## 📖 Käyttö

1.  **Vie Tiedot**: Lataa terveystietosi Maisasta ("Tilanneyhteenveto"). Kun olet purkanut ZIP-tiedoston, näet seuraavan kansion rakenteen:

    ```
    Tilanneyhteenveto_PP_Kuukausi_VVVV/
    ├── HTML/
    │   ├── IMAGES/
    │   └── STYLE/
    ├── IHE_XDM/
    │   └── <PotilasKansio>/     ← Tämä kansio sisältää XML-tiedostot!
    │       ├── DOC0001.XML
    │       ├── DOC0002.XML
    │       ├── ...
    │       ├── METADATA.XML
    │       └── STYLE.XSL
    ├── INDEX.HTM
    └── README - Open for Instructions.TXT
    ```

    > [!TÄRKEÄÄ]
    > Osoita jäsennin **`IHE_XDM/<PotilasKansio>/`** -hakemistoon, joka sisältää `DOC*.XML`-tiedostot, **ei** puretun kansion juureen.

2.  **Suorita Jäsennin**:

    ```bash
    python src/maisa_parser.py /polku/kohteeseen/IHE_XDM/<PotilasKansio>/
    ```

    Esimerkiksi:
    ```bash
    python src/maisa_parser.py ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/xxx/
    ```

    Jos suoritat skriptin datakansion sisältä, et tarvitse argumentteja:

    ```bash
    cd ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/xxx/
    python /polku/kohteeseen/maisa-parser/src/maisa_parser.py
    ```

3.  **Tarkastele Tulostetta**: Skripti luo `patient_history.json`-tiedoston nykyiseen työhakemistoosi.

## 📂 Tulosteen Rakenne

Luotu JSON sisältää:

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
      "provider": "Lääkärin Nimi",
      "notes": "Käynnin vapaamuotoinen teksti...",
      "source_file": "DOC0018.XML"
    },
    ...
  ]
}
```

## ⚠️ Tärkeä Huomautus Yksityisyydestä

Tämä työkalu käsittelee **arkaluonteisia terveystietoja**.
- **Älä vie (commit)** XML-tietojasi tai luotua JSON-tulostetta GitHubiin tai mihinkään julkiseen repositorioon.
- Mukana on `.gitignore`-tiedosto, joka auttaa estämään `.XML` ja `.json` -tiedostojen vahingossa tapahtuvan viennin.
- Käsittele terveystietojasi aina huolellisesti.

## 📥 Kuinka viedä tietosi Maisasta

1.  Kirjaudu sisään osoitteessa **[Maisa.fi](https://www.maisa.fi)**.
2.  Mene valikkoon **Valikko** > **Jakaminen** > **Lataa tietoni**.
3.  Valitse **"Lucy XML"** (tai "Kaikki").
4.  Lataa ZIP-tiedosto ja pura se.
5.  Näet kansion `IHE_XDM`, joka sisältää `DOC*.XML`-tiedostot. Tämä on kansio, jota käsitellään.

## ⚠️ Vastuuvapauslauseke

**Vastuuvapauslauseke:** Tämä ohjelmisto on tarkoitettu **vain koulutus- ja tietotarkoituksiin**. Se **ei** ole lääkinnällinen laite, eikä sitä tule käyttää diagnosointiin tai hoitoon. Kysy aina neuvoa terveydenhuollon ammattilaiselta. Tekijät eivät ole vastuussa jäsennysvirheistä tai tietojen esitystavasta.

Käyttämällä tätä työkalua hyväksyt, että olet yksin vastuussa omien terveystietojesi suojaamisesta.

## 🤝 Osallistuminen

Voit vapaasti lähettää virheraportteja (issues) tai pull request -pyyntöjä, jos löydät virheitä tai haluat parantaa jäsennyslogiikkaa erityyppisille Maisa-dokumenteille.
