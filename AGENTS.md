# Windows DOCX rendering notes

When rendering DOCX files with LibreOffice (`soffice`) on Windows:

- Build the isolated profile URI with `Path(profile_dir).as_uri()`. It must use
  `file:///C:/...`, never `file://C:\...`.
- If `shutil.which("soffice")` fails, check
  `C:\Program Files\LibreOffice\program\soffice.exe` before concluding that
  LibreOffice is unavailable.
- Use a unique temporary `UserInstallation` directory for every headless
  conversion.
- Add the bundled runtime's native Poppler directory to `PATH` before calling
  `pdf2image`; both `pdfinfo` and `pdftoppm` are required.
- Judge conversion by the generated PDF/PNG files. The warning
  `Could not find platform independent libraries <prefix>` is not itself a
  conversion failure.
- Plugin cache upgrades can overwrite local fixes in `render_docx.py`; reapply
  the URI, LibreOffice discovery, and Poppler fixes to the active plugin version
  when necessary.
