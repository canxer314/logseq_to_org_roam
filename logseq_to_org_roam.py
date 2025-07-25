#!/usr/bin/env python3
"""
Logseq to Org-roam Migration Script
==================================

This script migrates Logseq markdown files to org-roam format with comprehensive
handling of structure, content, and references.

Features:
- Preserves folder structure (assets, journals, pages)
- Converts hierarchical markdown lists to org-mode headings
- Handles double links, block references, and embeddings
- Migrates tasks, properties, and attachments
- Creates missing pages automatically
- Maintains asset references
- Complete markdown syntax conversion
- Enhanced double link detection and processing
"""

import os
import re
import shutil
import uuid
import yaml
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict
import argparse
import logging
from datetime import datetime

class LogseqToOrgRoamConverter:
    def __init__(self, logseq_dir: str, output_dir: str, verbose: bool = False):
        self.logseq_dir = Path(logseq_dir)
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        
        # Setup logging
        self.setup_logging()
        
        # ID mappings for org-roam
        self.page_ids: Dict[str, str] = {}
        self.block_ids: Dict[str, str] = {}
        self.existing_pages: Set[str] = set()
        self.missing_pages: Set[str] = set()
        self.file_to_title: Dict[str, str] = {}  # Map filename to actual title
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'missing_pages_created': 0,
            'assets_copied': 0,
            'errors': [],
            'warnings': []
        }
        
        # Task state mappings
        self.task_states = {
            'TODO': 'TODO',
            'DONE': 'DONE', 
            'LATER': 'LATER',
            'NOW': 'TODO',
            'DOING': 'DOING',
            'WAITING': 'WAITING',
            'CANCELLED': 'CANCELLED',
            'OVERDUE': 'TODO'
        }
        
        # Create output directories
        self.create_output_structure()
    
    def setup_logging(self):
        """Setup logging configuration"""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logseq_migration.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_output_structure(self):
        """Create the output directory structure"""
        for folder in ['assets', 'journals', 'pages']:
            (self.output_dir / folder).mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created output structure in {self.output_dir}")
    
    def generate_uuid(self) -> str:
        """Generate a UUID for org-roam"""
        return str(uuid.uuid4())
    
    def normalize_page_name(self, page_name: str) -> str:
        """Normalize page name for file operations"""
        # Remove markdown formatting
        page_name = re.sub(r'[*`~]', '', page_name)
        # Handle namespaces: convert / to ___
        page_name = page_name.replace('/', '___')
        # Clean up any remaining problematic characters, but preserve underscores
        page_name = re.sub(r'[<>:"|?*]', '', page_name)
        return page_name.strip()
    
    def scan_existing_pages(self):
        """First pass: scan all existing pages and extract titles"""
        self.logger.info("Scanning existing pages...")
        
        for folder in ['pages', 'journals']:
            folder_path = self.logseq_dir / folder
            if not folder_path.exists():
                continue
                
            for file_path in folder_path.glob('*.md'):
                page_name = file_path.stem
                self.existing_pages.add(page_name)
                self.page_ids[page_name] = self.generate_uuid()
                
                # Try to extract actual title from file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Look for title in YAML frontmatter or first heading
                    title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
                    if title_match:
                        self.file_to_title[page_name] = title_match.group(1).strip()
                    else:
                        # Look for first heading
                        heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                        if heading_match:
                            self.file_to_title[page_name] = heading_match.group(1).strip()
                        else:
                            self.file_to_title[page_name] = page_name
                
                except Exception as e:
                    self.file_to_title[page_name] = page_name
                    self.stats['warnings'].append(f"Could not extract title from {file_path}: {e}")
        
        self.logger.info(f"Found {len(self.existing_pages)} existing pages")
    
    def collect_missing_pages(self):
        """Second pass: collect all missing page references with enhanced detection"""
        self.logger.info("Collecting missing page references...")
        
        # Multiple regex patterns to catch different variations
        link_patterns = [
            r'\[\[([^\]]+?)\]\]',  # Standard [[page]] links
            r'\[\[([^\]|]+?)\|[^\]]*?\]\]',  # [[page|alias]] links (capture page part)
            r'\[\[([^\]]+?)\]\]\([^)]*?\)',  # [[page]](info) links
            r'{{embed\s+\[\[([^\]]+?)\]\]}}',  # Embedded links
            r'{{embed\s+\(\(([^)]+?)\)\)}}',  # Embedded block references
        ]
        
        # Additional patterns for edge cases
        edge_case_patterns = [
            r'(?:^|\s)\[\[([^\]]+?)\]\](?:\s|$)',  # Links at word boundaries
            r'(?<=\s)\[\[([^\]]+?)\]\](?=\s)',     # Links surrounded by spaces
            r'(?<=^)\[\[([^\]]+?)\]\]',            # Links at line start
            r'\[\[([^\]]+?)\]\](?=$)',             # Links at line end
            r'(?<=\n)\[\[([^\]]+?)\]\]',           # Links after newline
            r'\[\[([^\]]+?)\]\](?=\n)',            # Links before newline
        ]
        
        all_patterns = link_patterns + edge_case_patterns
        
        for folder in ['pages', 'journals']:
            folder_path = self.logseq_dir / folder
            if not folder_path.exists():
                continue
                
            for file_path in folder_path.glob('*.md'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Apply all patterns
                    for pattern in all_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            # Handle tuple results from some patterns
                            if isinstance(match, tuple):
                                match = match[0] if match[0] else match[1]
                            
                            # Clean the page name
                            page_name = self.normalize_page_name(match)
                            if page_name and page_name not in self.existing_pages:
                                self.missing_pages.add(page_name)
                                self.logger.debug(f"Found missing page reference: {page_name}")
                
                except Exception as e:
                    self.stats['errors'].append(f"Error reading {file_path}: {e}")
        
        self.logger.info(f"Found {len(self.missing_pages)} missing pages")
        if self.missing_pages and self.verbose:
            self.logger.info(f"Missing pages examples: {list(self.missing_pages)[:10]}")
    
    def create_missing_pages(self):
        """Create stub pages for missing references"""
        self.logger.info("Creating missing pages...")
        
        for page_name in self.missing_pages:
            page_id = self.generate_uuid()
            self.page_ids[page_name] = page_id
            
            # Create stub content
            stub_content = f""":PROPERTIES:
:ID: {page_id}
:END:
#+TITLE: {page_name}
#+FILETAGS: :stub:

This page was automatically created during Logseq migration on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
"""
            
            # Write stub file
            output_path = self.output_dir / 'pages' / f'{page_name}.org'
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(stub_content)
                self.stats['missing_pages_created'] += 1
                self.logger.debug(f"Created stub page: {page_name}")
            except Exception as e:
                self.stats['errors'].append(f"Error creating stub page {page_name}: {e}")
    
    def convert_markdown_to_org(self, content: str) -> str:
        """Convert markdown content to org-mode format with comprehensive syntax support"""
        # Use temporary tokens that don't conflict with markdown syntax
        temp_tokens = {
            'TEMP_CODE':   f'##TEMP_CODE_{uuid.uuid4().hex[:8]}##',
            'TEMP_BOLD':   f'##TEMP_BOLD_{uuid.uuid4().hex[:8]}##',
            'TEMP_ITALIC': f'##TEMP_ITALIC_{uuid.uuid4().hex[:8]}##',
            'TEMP_STRIKE': f'##TEMP_STRIKE_{uuid.uuid4().hex[:8]}##',
            'TEMP_LINK':   f'##TEMP_LINK_{uuid.uuid4().hex[:8]}##',
        }
        
        # Preserve existing org-mode elements temporarily
        org_elements = []
        def preserve_org(match):
            org_elements.append(match.group(0))
            return f'__ORG_ELEMENT_{len(org_elements)-1}__'
        
        # Preserve existing org-mode syntax
        content = re.sub(r'\[\[id:[^\]]+\]\[[^\]]+\]\]', preserve_org, content)
        content = re.sub(r'^\*+\s+.*$', preserve_org, content, flags=re.MULTILINE)
        
        # Headers (convert before other formatting to avoid conflicts)
        content = re.sub(r'^(#{1,6})\s+(.+)$', lambda m: '*' * len(m.group(1)) + ' ' + m.group(2), content, flags=re.MULTILINE)
        
        # Horizontal rules
        content = re.sub(r'^---+$', '-----', content, flags=re.MULTILINE)
        
        # Code blocks (handle both with and without language)
        content = re.sub(r'^```(\w+)?\n(.*?)\n```$', 
                        lambda m: f'#+BEGIN_SRC {m.group(1) or ""}\n{m.group(2)}\n#+END_SRC', 
                        content, flags=re.MULTILINE | re.DOTALL)
        
        # Quote blocks (handle multi-line quotes)
        content = re.sub(r'^>\s*(.+)(?:\n^>\s*(.+))*', 
                        lambda m: f'#+BEGIN_QUOTE\n{m.group(0).replace("> ", "").replace(">", "")}\n#+END_QUOTE', 
                        content, flags=re.MULTILINE)
        
        # Text formatting (using temporary tokens to avoid conflicts)
        # The order is important to prevent conflicts.
        
        # Code: `code` (first, as it can contain other symbols)
        content = re.sub(r'`([^`\n]+?)`', f'{temp_tokens["TEMP_CODE"]}\\1{temp_tokens["TEMP_CODE"]}', content)

        # Bold: **text** or __text__
        content = re.sub(r'\*\*([\s\S]+?)\*\*', f'{temp_tokens["TEMP_BOLD"]}\\1{temp_tokens["TEMP_BOLD"]}', content)
        content = re.sub(r'__([\s\S]+?)__', f'{temp_tokens["TEMP_BOLD"]}\\1{temp_tokens["TEMP_BOLD"]}', content)

        # Italic: *text* or _text_
        # The lookarounds prevent matching parts of bold markers or words with underscores.
        content = re.sub(r'(?<!\*)\*([\s\S]+?)\*(?!\*)', f'{temp_tokens["TEMP_ITALIC"]}\\1{temp_tokens["TEMP_ITALIC"]}', content)
        content = re.sub(r'(?<![a-zA-Z0-9_])_([\s\S]+?)_(?![a-zA-Z0-9_])', f'{temp_tokens["TEMP_ITALIC"]}\\1{temp_tokens["TEMP_ITALIC"]}', content)
        
        # Strikethrough: ~~text~~
        content = re.sub(r'~~([^~\n]+?)~~', f'{temp_tokens["TEMP_STRIKE"]}\\1{temp_tokens["TEMP_STRIKE"]}', content)
        
        # Regular markdown links [text](url)
        content = re.sub(r'(?<!\[)\[([^\]]+?)\]\(([^)]+?)\)', 
                         lambda m: f'{temp_tokens["TEMP_LINK"]}[{m.group(2)}][{m.group(1)}]{temp_tokens["TEMP_LINK"]}', 
                         content)

        # Tables
        content = self.convert_tables(content)
        
        # Lists (preserve structure for later hierarchical conversion)
        # This is handled separately in convert_hierarchical_structure
        
        # Replace temporary tokens with org-mode formatting
        content = content.replace(temp_tokens["TEMP_CODE"], '=')
        content = content.replace(temp_tokens["TEMP_BOLD"], '*')
        content = content.replace(temp_tokens["TEMP_ITALIC"], '/')
        content = content.replace(temp_tokens["TEMP_STRIKE"], '+')
        content = re.sub(f'{re.escape(temp_tokens["TEMP_LINK"])}\[(.*?)\]\[(.*?)\]{re.escape(temp_tokens["TEMP_LINK"])}',
                         r'[[\1][\2]]',
                         content)

        # Restore preserved org-mode elements
        for i, element in enumerate(org_elements):
            content = content.replace(f'__ORG_ELEMENT_{i}__', element)

        return content
    
    def convert_tables(self, content: str) -> str:
        """Convert markdown tables to org-mode tables with proper formatting"""
        lines = content.split('\n')
        result = []
        in_table = False
        
        i = 0
        while i < len(lines):
            original_line = lines[i]
            stripped_line = original_line.strip()
            
            # Check if this line starts a table
            if re.match(r'^\|.*\|$', stripped_line):
                if not in_table:
                    in_table = True
                
                # Convert table row
                cells = [cell.strip() for cell in stripped_line.split('|')[1:-1]]
                result.append('| ' + ' | '.join(cells) + ' |')
                
                # Check if next line is a separator
                if i + 1 < len(lines):
                    next_line_stripped = lines[i + 1].strip()
                    if re.match(r'^\|[-\s|:]+\|$', next_line_stripped):
                        # Add org-mode table separator
                        result.append('|' + '-' * (len(stripped_line) - 2) + '|')
                        i += 1  # Skip the separator line
                
            elif in_table and not re.match(r'^\|.*\|$', stripped_line):
                # End of table
                in_table = False
                result.append(original_line)
            else:
                result.append(original_line)
            
            i += 1
        
        return '\n'.join(result)
    
    def convert_hierarchical_structure(self, content: str) -> str:
        """Convert markdown unordered lists to org-mode headings with proper nesting"""
        lines = content.split('\n')
        result = []
        
        for line in lines:
            # Match unordered list items with indentation
            match = re.match(r'^(\s*)-\s+(.+)$', line)
            if match:
                indent_str = match.group(1)
                # Calculate indent by counting tabs (1 tab = 2 spaces) and spaces separately
                tab_count = indent_str.count('\t') * 2  # Each tab counts as 2 spaces
                space_count = indent_str.count(' ')
                indent = tab_count + space_count
                text = match.group(2)
                
                # Convert to org-mode heading based on indentation level
                # Each 2 spaces of indentation = 1 heading level
                level = (indent // 2) + 1
                level = min(level, 6)  # Org-mode supports up to 6 levels
                
                # Also handle task conversion here to get the level right
                
                # Check for checkboxes first
                checkbox_match = re.match(r'\[( |x|X)\]\s+(.+)', text)
                if checkbox_match:
                    state = checkbox_match.group(1)
                    task_text = checkbox_match.group(2)
                    org_state = 'DONE' if state.lower() == 'x' else 'TODO'
                    heading = '*' * level + ' ' + org_state + ' ' + task_text
                    result.append(heading)
                    continue

                # Check for Logseq task keywords
                task_match = re.match(r'^(TODO|DONE|LATER|NOW|DOING|WAITING|CANCELLED|OVERDUE)\s+(.+)$', text)
                if task_match:
                    logseq_state = task_match.group(1)
                    task_text = task_match.group(2)
                    org_state = self.task_states.get(logseq_state, 'TODO')
                    heading = '*' * level + ' ' + org_state + ' ' + task_text
                    result.append(heading)
                    continue

                # If not a task, just a regular heading
                heading = '*' * level + ' ' + text
                result.append(heading)
            else:
                result.append(line)
        
        return '\n'.join(result)
    
    def convert_tasks(self, content: str) -> str:
        """Convert Logseq tasks to org-mode tasks with proper formatting"""
        # This logic is now handled by convert_hierarchical_structure to ensure
        # correct heading levels are applied.
        return content
    
    def convert_double_links(self, content: str) -> str:
        """Convert double links to org-roam format with enhanced detection"""
        def replace_link(match):
            link_text = match.group(1)
            
            # Handle aliases [[page|alias]]
            if '|' in link_text:
                page_name, alias = link_text.split('|', 1)
                page_name = page_name.strip()
                alias = alias.strip()
            else:
                page_name = link_text.strip()
                alias = page_name
            
            # Normalize page name
            normalized_name = self.normalize_page_name(page_name)
            
            # Get or create page ID
            if normalized_name in self.page_ids:
                page_id = self.page_ids[normalized_name]
            else:
                # Fallback: create ID on the fly and add to missing pages
                page_id = self.generate_uuid()
                self.page_ids[normalized_name] = page_id
                self.missing_pages.add(normalized_name)
                self.logger.warning(f"Creating fallback ID for missing page: {normalized_name}")
            
            return f'[[id:{page_id}][{alias}]]'
        
        # Convert double links with multiple patterns for robustness
        patterns = [
            r'\[\[([^\]]+?)\]\]',  # Standard pattern
            r'\[\[([^\]]+?)\]\](?!\])',  # Ensure not part of larger structure
        ]
        
        for pattern in patterns:
            content = re.sub(pattern, replace_link, content)
        
        return content
    
    def convert_block_references(self, content: str) -> str:
        """Convert block references to org-mode format"""
        def replace_block_ref(match):
            block_ref = match.group(1)
            if block_ref not in self.block_ids:
                self.block_ids[block_ref] = self.generate_uuid()
            return f'[[id:{self.block_ids[block_ref]}]]'
        
        # Block references ((block-ref)) -> [[id:block-id]]
        content = re.sub(r'\(\(([^)]+?)\)\)', replace_block_ref, content)
        
        return content
    
    def convert_block_embeddings(self, content: str) -> str:
        """Convert block embeddings to org-mode includes"""
        def replace_embed(match):
            embed_content = match.group(1)
            
            # Extract page name from embed
            page_match = re.search(r'\[\[([^\]]+?)\]\]', embed_content)
            if page_match:
                page_name = self.normalize_page_name(page_match.group(1))
                return f'#+INCLUDE: "{page_name}.org"'
            
            # Handle block reference embeds
            block_match = re.search(r'\(\(([^)]+?)\)\)', embed_content)
            if block_match:
                block_ref = block_match.group(1)
                if block_ref not in self.block_ids:
                    self.block_ids[block_ref] = self.generate_uuid()
                return f'#+INCLUDE: "[[id:{self.block_ids[block_ref]}]]"'
            
            return match.group(0)  # Return original if can't parse
        
        # Block embeddings {{embed [[page]]}} or {{embed ((block))}}
        content = re.sub(r'{{embed\s+([^}]+?)}}', replace_embed, content, flags=re.IGNORECASE)
        
        return content
    
    def extract_properties(self, content: str) -> Tuple[Dict[str, str], str]:
        """Extract YAML frontmatter and inline properties"""
        properties = {}
        
        # Extract YAML frontmatter
        yaml_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if yaml_match:
            try:
                yaml_content = yaml.safe_load(yaml_match.group(1))
                if isinstance(yaml_content, dict):
                    properties.update(yaml_content)
                content = yaml_match.group(2)
            except yaml.YAMLError as e:
                self.stats['warnings'].append(f"Error parsing YAML frontmatter: {e}")
        
        # Extract inline properties (property:: value)
        inline_props = re.findall(r'^(\w+)::\s*(.+)$', content, re.MULTILINE)
        for prop, value in inline_props:
            properties[prop] = value
        
        # Remove inline properties from content
        content = re.sub(r'^(\w+)::\s*(.+)$', '', content, flags=re.MULTILINE)
        
        # Clean up empty lines
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        return properties, content
    
    def create_org_header(self, title: str, properties: Dict[str, str]) -> str:
        """Create org-roam header with properties"""
        page_id = self.page_ids.get(title, self.generate_uuid())
        
        header = f""":PROPERTIES:
:ID: {page_id}
"""
        
        # Add other properties
        for key, value in properties.items():
            if key.upper() not in ['ID', 'TITLE']:
                header += f":{key.upper()}: {value}\n"
        
        header += ":END:\n"
        header += f"#+TITLE: {title}\n"
        
        # Add filetags if any
        if 'tags' in properties:
            tags = properties['tags']
            if isinstance(tags, list):
                tags = ' '.join(f':{tag}:' for tag in tags)
            elif isinstance(tags, str):
                if not tags.startswith(':'):
                    tags = f':{tags}:'
            header += f"#+FILETAGS: {tags}\n"
        
        return header + "\n"
    
    def update_asset_paths(self, content: str) -> str:
        """Update asset paths in content to maintain references"""
        # Update image references
        content = re.sub(r'!\[(.*?)\]\(\.\./assets/([^)]+?)\)', r'![\1](../assets/\2)', content)
        content = re.sub(r'!\[(.*?)\]\(assets/([^)]+?)\)', r'![\1](../assets/\2)', content)
        
        # Update file references
        content = re.sub(r'\[(.*?)\]\(\.\./assets/([^)]+?)\)', r'[\1](../assets/\2)', content)
        content = re.sub(r'\[(.*?)\]\(assets/([^)]+?)\)', r'[\1](../assets/\2)', content)
        
        return content
    
    def convert_file(self, file_path: Path, output_path: Path):
        """Convert a single markdown file to org-mode"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.logger.debug(f"Converting file: {file_path}")
            
            # Extract properties first
            properties, content = self.extract_properties(content)
            
            # Get title (use from properties, file mapping, or filename)
            title = properties.get('title') or self.file_to_title.get(file_path.stem, file_path.stem)
            
            # Convert content in proper order
            content = self.convert_markdown_to_org(content)
            content = self.convert_tasks(content)
            content = self.convert_hierarchical_structure(content)
            content = self.convert_double_links(content)
            content = self.convert_block_references(content)
            content = self.convert_block_embeddings(content)
            content = self.update_asset_paths(content)
            
            # Create org-roam header
            header = self.create_org_header(title, properties)
            
            # Combine header and content
            org_content = header + content.strip()
            
            table_pattern = r'(^(\*)+[ ])\|(.*)'
            table_replacement = r'\1table \n|\3'
            # print(f"  before: {org_content}")
            org_content = re.sub(table_pattern, table_replacement, org_content, flags=re.MULTILINE)
            # print(f"  after: {org_content}")

            dash_pattern = r'(\d\d\d\d)_(\d\d)_(\d\d)'
            dash_replacement = r'\1-\2-\3'
            org_content = re.sub(dash_pattern, dash_replacement, org_content, flags=re.MULTILINE)

            # Write output file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(org_content)
            
            self.stats['files_processed'] += 1
            self.logger.debug(f"Successfully converted: {file_path} -> {output_path}")
            
        except Exception as e:
            error_msg = f"Error converting {file_path}: {e}"
            self.stats['errors'].append(error_msg)
            self.logger.error(error_msg)
    
    def copy_assets(self):
        """Copy all assets to output directory"""
        assets_dir = self.logseq_dir / 'assets'
        if not assets_dir.exists():
            self.logger.info("No assets directory found, skipping asset copy")
            return
        
        output_assets = self.output_dir / 'assets'
        
        try:
            if output_assets.exists():
                shutil.rmtree(output_assets)
            
            shutil.copytree(assets_dir, output_assets)
            
            # Count copied files
            copied_files = list(output_assets.rglob('*'))
            self.stats['assets_copied'] = len([f for f in copied_files if f.is_file()])
            
            self.logger.info(f"Copied {self.stats['assets_copied']} asset files")
            
        except Exception as e:
            error_msg = f"Error copying assets: {e}"
            self.stats['errors'].append(error_msg)
            self.logger.error(error_msg)
    
    def convert_all(self):
        """Main conversion process with comprehensive 3-pass approach"""
        self.logger.info(f"Starting Logseq to org-roam conversion")
        self.logger.info(f"Source: {self.logseq_dir}")
        self.logger.info(f"Target: {self.output_dir}")
        
        # Three-pass approach for complete reference resolution
        self.logger.info("=== PASS 1: Scanning existing pages ===")
        self.scan_existing_pages()
        
        self.logger.info("=== PASS 2: Collecting missing page references ===")
        self.collect_missing_pages()
        
        self.logger.info("=== PASS 3: Creating missing pages ===")
        self.create_missing_pages()
        
        # Convert existing files
        self.logger.info("=== CONVERTING FILES ===")
        
        total_files = 0
        for folder in ['pages', 'journals']:
            folder_path = self.logseq_dir / folder
            if folder_path.exists():
                total_files += len(list(folder_path.glob('*.md')))
        
        self.logger.info(f"Converting {total_files} files...")
        
        for folder in ['pages', 'journals']:
            folder_path = self.logseq_dir / folder
            if not folder_path.exists():
                continue
                
            output_folder = self.output_dir / folder
            
            for file_path in folder_path.glob('*.md'):
                dash_pattern = r'(\d\d\d\d)_(\d\d)_(\d\d)'
                dash_replacement = r'\1-\2-\3'
                final_stem = re.sub(dash_pattern, dash_replacement, file_path.stem, flags=re.MULTILINE)
                output_file = output_folder / (final_stem + '.org')
                self.convert_file(file_path, output_file)
        
        # Copy assets
        self.logger.info("=== COPYING ASSETS ===")
        self.copy_assets()
        
        # Print results
        self.print_summary()
    
    def print_summary(self):
        """Print comprehensive conversion summary"""
        print("\n" + "="*60)
        print("LOGSEQ TO ORG-ROAM CONVERSION SUMMARY")
        print("="*60)
        print(f"Source directory: {self.logseq_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"Conversion completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        print(f"Files processed: {self.stats['files_processed']}")
        print(f"Missing pages created: {self.stats['missing_pages_created']}")
        print(f"Assets copied: {self.stats['assets_copied']}")
        print(f"Warnings: {len(self.stats['warnings'])}")
        print(f"Errors: {len(self.stats['errors'])}")
        
        if self.stats['warnings'] and self.verbose:
            print("\nWarnings:")
            for warning in self.stats['warnings'][:5]:
                print(f"  ⚠ {warning}")
            if len(self.stats['warnings']) > 5:
                print(f"  ... and {len(self.stats['warnings']) - 5} more warnings")
        
        if self.stats['errors']:
            print("\nErrors:")
            for error in self.stats['errors'][:5]:
                print(f"  ❌ {error}")
            if len(self.stats['errors']) > 5:
                print(f"  ... and {len(self.stats['errors']) - 5} more errors")
        
        print("-"*60)
        if self.stats['errors']:
            print("⚠ Conversion completed with errors. Check the log file for details.")
        else:
            print("✅ Conversion completed successfully!")
        
        print(f"📁 Files saved to: {self.output_dir}")
        print(f"📋 Log file: logseq_migration.log")

def main():
    parser = argparse.ArgumentParser(
        description='Convert Logseq files to org-roam format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python logseq_to_org_roam.py /path/to/logseq /path/to/org-roam
  python logseq_to_org_roam.py ./logseq ./org-roam --verbose
        """
    )
    parser.add_argument('input_dir', help='Path to Logseq directory')
    parser.add_argument('output_dir', help='Path to output directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output with debug information')
    
    args = parser.parse_args()
    
    # Validate input directory
    if not os.path.exists(args.input_dir):
        print(f"❌ Error: Input directory '{args.input_dir}' does not exist")
        return 1
    
    # Check if input directory looks like a Logseq directory
    input_path = Path(args.input_dir)
    if not any((input_path / folder).exists() for folder in ['pages', 'journals']):
        print(f"⚠ Warning: '{args.input_dir}' doesn't appear to be a Logseq directory")
        print("Expected to find 'pages' or 'journals' folders")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return 1
    
    # Create converter and run
    try:
        converter = LogseqToOrgRoamConverter(args.input_dir, args.output_dir, args.verbose)
        converter.convert_all()
        return 0
    except KeyboardInterrupt:
        print("\n❌ Conversion interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())