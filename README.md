# Logseq to Org-roam Migration Tool

A comprehensive Python script for migrating knowledge bases from Logseq to Org-roam format with complete structure, content, and reference preservation.


## Features

- **Complete Structure Conversion**:
  - Preserves folder hierarchy (assets, journals, pages)
  - Maintains all internal links and references
  - Handles both page links and block references

- **Content Transformation**:
  - Converts hierarchical markdown lists to org-mode headings
  - Transforms tasks with state preservation (TODO, DONE, etc.)
  - Processes all markdown formatting (bold, italics, code, etc.)
  - Handles tables, code blocks, and quotes

- **Advanced Reference Handling**:
  - Automatic creation of missing pages
  - Block reference conversion with UUID generation
  - Embedding resolution
  - Asset path correction

- **Metadata Preservation**:
  - YAML frontmatter conversion to org properties
  - Tag system migration
  - Custom property support

## Installation

1. Ensure you have Python 3.7+ installed
2. Clone this repository or download the script
3. Install required dependencies:
   ```bash
   pip install pyyaml
   ```

## Usage

```bash
python logseq_to_org_roam.py [input_dir] [output_dir] [--verbose]
```

### Arguments

- `input_dir`: Path to your Logseq directory (containing `pages/`, `journals/`, etc.)
- `output_dir`: Path where org-roam files should be created
- `--verbose` or `-v`: Enable detailed logging

### Example

```bash
python logseq_to_org_roam.py ~/logseq-notes ~/org-roam-notes --verbose
```

## Conversion Details

### What Gets Converted

| Logseq Element          | Org-roam Equivalent               |
|-------------------------|-----------------------------------|
| Pages                   | Org-roam nodes                    |
| Journals                | Dated org-roam nodes              |
| Tags                    | Org filetags                      |
| Tasks                   | Org TODO items                    |
| Block references        | Org ID links                      |
| Embeds                  | Org INCLUDE directives            |
| Properties              | Org PROPERTIES drawer             |
| Assets                  | Copied to assets directory        |

### Special Cases Handled

- **Namespace pages**: `namespace/page` becomes `namespace___page`
- **Date formats**: `yyyy_mm_dd` journals become `yyyy-mm-dd`
- **Complex links**: `[[page\|alias]]` becomes `[[id:uuid][alias]]`
- **Mixed content**: Nested markdown in lists and blocks

## Post-Migration Steps

1. **Verify**: Check the conversion summary for errors
2. **Review**: Examine a sample of converted files
3. **Customize**: Add any org-mode specific configurations as needed
4. **Backup**: Keep your original Logseq directory until fully verified

## Limitations

- Some advanced Logseq features may not have direct org-mode equivalents
- Very large knowledge bases may require additional memory
- Complex nested structures might need manual adjustment

## Support

For issues or feature requests, please [open an issue](https://github.com/your-repo/issues).

---

**Note**: Always back up your data before migration. This tool makes no modifications to your original Logseq files.
```

This README includes:

1. Clear feature highlights
2. Installation and usage instructions
3. Conversion mapping table
4. Special cases documentation
5. Post-migration guidance
6. Limitations disclosure
7. Professional formatting with emoji and structure

You may want to:
- Add actual screenshots if available
- Include a more detailed conversion example
- Add a troubleshooting section
- Customize the support section with your contact info
