# Data

`requirements.csv` holds 32 requirements (R01-R33, R17 is not in the source) taken from the
KeePass Password Safe SRS (release 1.10), file `2008 - keepass.xml` in the PURE dataset.
`project.txt` is a short description of that system, used as context in the prompts.

**Source:** PURE, a dataset of public requirements documents, Ferrari et al.
Zenodo, DOI 10.5281/zenodo.1414117, https://zenodo.org/records/1414117, licence CC BY 4.0.

The requirement text is unchanged from the dataset. Only the format was changed (XML to CSV with
columns `id,text`). To run on another PURE document, make a CSV with the same two columns and
pass it with `--data`, plus a short description file with `--project`.
