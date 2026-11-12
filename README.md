# Metacheck reports for medRxiv preprints

The reports are at **https://lakens.github.io/medrxiv_metacheck/**. Search by title, author or medRxiv number (such as 2026.04.04.26349881) to find a preprint.

The goal of this project is to automatically generate Metacheck reports for medRxiv preprints. This service helps authors to see what they can improve in their preprints before submission. Automated checks have false positives. Despite extensive validation efforts (see our [values](https://www.scienceverse.org/metacheck_book/chapters/intro.html#our-values)), false positives will be present. Another goal of this project is to check a large number of real papers and identify where Metacheck can be improved. Do not take a classification of 'something to fix' as a certain guarantee that the paper has a problem. Metacheck is intended to assist people, not replace them. It is designed like a spellchecker: it might have false positives, but the cost-benefit analysis of using the tool should be positive through the real mistakes it identifies.

The same reports for PsyArXiv preprints are at https://lakens.github.io/psyarxiv_metacheck/.

## About Metacheck

Metacheck screens scientific manuscripts to identify potential issues or areas for improvement and guide researchers in adopting best practices. It is a module based [open source tool](https://github.com/scienceverse/metacheck). For information on the available modules, see the [manual](https://www.scienceverse.org/metacheck_book/). The reports are automated: they miss things and flag things that are fine, so read every finding as a question, not a verdict. If you find an error, please [leave an issue on GitHub](https://github.com/scienceverse/metacheck/issues) or email us at [metacheck@scienceverse.org](mailto:metacheck@scienceverse.org). You can run Metacheck on your own paper on [our server](https://metacheckserve.metacheck.src.surf-hosted.nl). We thank [SURF](https://www.surf.nl/en/services/surf-research-cloud) for SURF Research Cloud, on which these checks run. If Metacheck was useful in improving your preprint, you can cite it as:

DeBruine, L., Mesquida, C., Werner, J., & Lakens, D. (2026). *Metacheck: Check research outputs for best practices* [Computer software]. https://doi.org/10.5281/zenodo.20704754

## How it works

A program in this repository (`scripts/update.py`) asks medRxiv's listing service for the preprints posted on medRxiv. It downloads each preprint's PDF from medRxiv and sends it to the Metacheck server on SURF Research Cloud. The server runs Metacheck's 16 checks, which includes looking at the data and code in repositories the paper links to and running the paper's R and Python code. The program then stores the result in this repository and adds the report to the website.

The program runs without interruption: when one run ends, the next one starts, and each run looks for newly posted preprints every 10 minutes when nothing is waiting. New preprints are checked first, the most recent first. When no new preprint is waiting, the program checks older preprints, one day at a time going back. A preprint is checked in its newest version at that moment. A later version gets its own report, and the reports on older versions stay.

The program sends one preprint at a time, and only when nobody else is using the server, so that people who check their own paper on the server do not have to wait for us. The server also checks PsyArXiv preprints for the PsyArXiv site; the two take turns. A check takes a few minutes, and up to about an hour when the paper's code is run (the server stops code after 60 minutes). A new preprint will usually have its report within a few days of being posted, but it can take longer when many preprints are posted at once or when the server is busy. Preprints are not checked when they have been withdrawn, or when their PDF is larger than 50 MB. If you cannot find your preprint after a few days, please [leave an issue](https://github.com/lakens/medrxiv_metacheck/issues).

## Licences

Many medRxiv preprints have a licence that does not allow others to share them. The report on a preprint shows the paper's full text, as Metacheck read it, only when its licence allows sharing: CC BY, CC BY-NC, or CC0. For other licences (CC BY-ND, CC BY-NC-ND, or no reuse), the full text is not shown and not stored in this repository; the report itself, which quotes the sentences each check is about, is shown for every preprint.
