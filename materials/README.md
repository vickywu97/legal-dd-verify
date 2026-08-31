# materials/ — synthetic data-room reference

The 29 files in this directory are the **synthetic** data room used to develop and QA
the legal-dd-verify pipeline. They are provided as a **schema reference** of the kind of
input the pipeline consumes.

- These files are **entirely fictional and synthetically generated**; **no real person,
  company, contract, or account data is present.** The authoritative synthetic disclaimer
  lives in the top-level `README.md`.
- These are **text-extracted views** of what would be PDF / XLSX / DOCX source files in a
  real run. The pipeline (`pipeline/extract.py`) reads **PDF / XLSX / DOCX**, not `.txt`.
- To execute the pipeline end-to-end, supply a data room in PDF/XLSX/DOCX format and point
  `--input` at it. The 4-file output of a real run is in the repo's top-level `examples/`.

Folder layout mirrors the diligence taxonomy:

```
00_索引与说明 / 01_主体资格及历史沿革 / 02_股权及公司治理 /
03_重大合同及融资 / 04_知识产权及信息技术 / 05_劳动人事 /
06_数据合规及业务资质 / 07_争议债务及保险 / 08_物业及其他
```
