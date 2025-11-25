"""
Hansard NSW Parliament Scraper

A lightweight web scraper for extracting Hansard (parliamentary debate records) data
from the NSW Parliament website using their official API.

This scraper uses direct API calls instead of Selenium, making it faster, more reliable,
and resource-efficient.

Author: Yulius Kurniawan Wijaya
License: MIT
"""

import json
import logging
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from colorama import Fore, Back, Style, init

# Initialize colorama for Windows
init(autoreset=True)

# Configure logging dengan custom formatter
class ColoredFormatter(logging.Formatter):
    """Custom formatter dengan warna dan emoji."""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Back.WHITE,
    }
    
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '✓',
        'WARNING': '⚠️',
        'ERROR': '✗',
        'CRITICAL': '🔥',
    }
    
    def format(self, record):
        levelname = record.levelname
        color = self.COLORS.get(levelname, '')
        emoji = self.EMOJIS.get(levelname, '')
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Format message dengan warna
        if hasattr(record, 'no_emoji'):
            formatted = f"{color}[{timestamp}]{Style.RESET_ALL} {record.getMessage()}"
        else:
            formatted = f"{color}{emoji} [{timestamp}]{Style.RESET_ALL} {record.getMessage()}"
        
        return formatted

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Remove existing handlers
logger.handlers = []

# Create console handler dengan custom formatter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredFormatter())
logger.addHandler(console_handler)

# Prevent propagation
logger.propagate = False


def print_header(title: str, char: str = '═', width: int = 70):
    """Print header yang menarik."""
    print(f"\n{Fore.CYAN}{char * width}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}{title.center(width)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{char * width}{Style.RESET_ALL}\n")


def print_subheader(title: str, width: int = 70):
    """Print subheader yang menarik."""
    print(f"\n{Fore.MAGENTA}{'─' * width}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}▶ {Style.BRIGHT}{title}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'─' * width}{Style.RESET_ALL}")


def print_info(label: str, value: any, indent: int = 0):
    """Print info dengan format yang rapi."""
    spaces = ' ' * indent
    print(f"{spaces}{Fore.CYAN}◆{Style.RESET_ALL} {Fore.WHITE}{label}:{Style.RESET_ALL} {Fore.GREEN}{value}{Style.RESET_ALL}")


def print_progress(current: int, total: int, item_name: str = "", extra: str = ""):
    """Print progress dengan bar yang menarik."""
    percentage = (current / total) * 100 if total > 0 else 0
    bar_length = 30
    filled_length = int(bar_length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    progress_text = f"{Fore.BLUE}[{current}/{total}]{Style.RESET_ALL}"
    bar_text = f"{Fore.GREEN}{bar}{Style.RESET_ALL}"
    percent_text = f"{Fore.YELLOW}{percentage:5.1f}%{Style.RESET_ALL}"
    
    if item_name:
        item_text = f"{Fore.WHITE}{item_name[:45]}{Style.RESET_ALL}"
        if len(item_name) > 45:
            item_text += "..."
    else:
        item_text = ""
    
    if extra:
        extra_text = f" {Fore.CYAN}({extra}){Style.RESET_ALL}"
    else:
        extra_text = ""
    
    print(f"  {progress_text} {bar_text} {percent_text} {item_text}{extra_text}")


# ============================================
# CONFIGURATION CONSTANTS
# ============================================

API_BASE_URL = "https://api.parliament.nsw.gov.au/api/hansard/search"
DEFAULT_TIMEOUT = 30
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/xml, text/xml, */*; q=0.01",
}


# ============================================
# UTILITY CLASSES
# ============================================

class DocumentIDExtractor:
    """Extracts document IDs from Hansard URLs."""
    
    HANSARD_ID_PATTERN = r"HANSARD-\d+-\d+"
    
    @classmethod
    def extract_from_url(cls, url: str) -> List[str]:
        """
        Extract Hansard document IDs from a URL.
        
        Args:
            url: The Hansard URL containing document IDs
            
        Returns:
            List containing the last document ID found
            
        Raises:
            ValueError: If no document ID is found in the URL
        """
        print(f"\n{Fore.CYAN}🔎 Extracting Document ID from URL...{Style.RESET_ALL}")
        doc_ids = re.findall(cls.HANSARD_ID_PATTERN, url)
        
        if not doc_ids:
            raise ValueError(f"{Fore.RED}✗ No Document ID found in URL!{Style.RESET_ALL}")
        
        last_doc_id = doc_ids[-1]
        print(f"{Fore.GREEN}✓ Using Document ID:{Style.RESET_ALL} {Fore.YELLOW}{last_doc_id}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  ℹ Total {len(doc_ids)} ID(s) found{Style.RESET_ALL}")
        
        return [last_doc_id]


class XMLParser:
    """Parses XML responses from the Hansard API."""
    
    @staticmethod
    def parse_table_of_contents(xml_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Parse the Table of Contents XML to extract tree structure and fragment UIDs.
        
        Args:
            xml_text: Raw XML response text
            
        Returns:
            Tuple of (branches list, fragment_uids dict)
        """
        soup = BeautifulSoup(xml_text, 'xml')
        branches = []
        fragment_uids = {}
        
        # Extract metadata from header
        metadata = XMLParser._extract_metadata(soup)
        
        # Create Level 1: House and Date
        level1_name = XMLParser._create_level1_name(metadata)
        branches.append({
            "name": level1_name,
            "level": 1,
            "path": level1_name,
            "text": "",
            "has_children": True
        })
        logger.info(f"📄 Level 1 created: {Fore.YELLOW}{level1_name}{Style.RESET_ALL}")
        
        # Parse all proceedings
        proceedings = soup.find_all('proceeding')
        logger.info(f"📋 Found {Fore.CYAN}{len(proceedings)}{Style.RESET_ALL} proceedings")
        
        for proceeding in proceedings:
            XMLParser._parse_proceeding(
                proceeding, level1_name, branches, fragment_uids
            )
        
        XMLParser._log_branch_summary(branches)
        logger.info(f"Total {len(fragment_uids)} fragment UIDs stored")
        
        return branches, fragment_uids
    
    @staticmethod
    def _extract_metadata(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract metadata from hansard.header."""
        metadata = {'date': None, 'house': None}
        
        header = soup.find('hansard.header')
        if header:
            date_elem = header.find('date')
            chamber_elem = header.find('chamber')
            
            if date_elem:
                date_text = date_elem.text.strip()
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                if date_match:
                    metadata['date'] = date_match.group(1)
            
            if chamber_elem:
                metadata['house'] = chamber_elem.text.strip()
        
        return metadata
    
    @staticmethod
    def _create_level1_name(metadata: Dict[str, Optional[str]]) -> str:
        """Create Level 1 name from metadata."""
        if metadata['house'] and metadata['date']:
            return f"{metadata['house']} ({metadata['date']})"
        return "Legislative Assembly (Unknown Date)"
    
    @staticmethod
    def _parse_proceeding(
        proceeding, 
        level1_name: str, 
        branches: List[Dict[str, Any]], 
        fragment_uids: Dict[str, str]
    ) -> None:
        """Parse a single proceeding element."""
        proceedinginfo = proceeding.find('proceedinginfo')
        if not proceedinginfo:
            return
        
        proceeding_name_elem = proceedinginfo.find('text')
        if not proceeding_name_elem:
            return
        
        level2_name = proceeding_name_elem.text.strip()
        level2_path = f"{level1_name} > {level2_name}"
        
        # Get all topics at this proceeding level
        topics = proceeding.find_all('topic', recursive=False)
        
        # Only create level 2 if there are topics
        if not topics:
            return
        
        # Check if this level2_path already exists
        existing_branch = None
        for branch in branches:
            if branch.get('level') == 2 and branch.get('path') == level2_path:
                existing_branch = branch
                break
        
        # If doesn't exist, create it
        if not existing_branch:
            branches.append({
                "name": level2_name,
                "level": 2,
                "path": level2_path,
                "text": "",
                "has_children": True
            })
        else:
            # Update has_children
            existing_branch["has_children"] = True
        
        # Parse all topics (Level 3) immediately after creating level 2
        for topic in topics:
            XMLParser._parse_topic(topic, level2_path, branches, fragment_uids)
    
    @staticmethod
    def _parse_topic(
        topic,
        level2_path: str,
        branches: List[Dict[str, Any]],
        fragment_uids: Dict[str, str]
    ) -> None:
        """Parse a topic element (Level 3)."""
        topic_uid = topic.get('uid')
        topicinfo = topic.find('topicinfo')
        
        if not topicinfo:
            return
        
        topic_text_elem = topicinfo.find('text')
        if not topic_text_elem:
            return
        
        level3_name = topic_text_elem.text.strip()
        level3_path = f"{level2_path} > {level3_name}"
        
        # Store fragment UID using the full path as key
        if topic_uid:
            fragment_uids[level3_path] = topic_uid
        
        # Check for children
        subproceedings = topic.find_all('subproceeding', recursive=False)
        speeches = topic.find_all('speech', recursive=False)
        questions = topic.find_all('question', recursive=False)
        answers = topic.find_all('answer', recursive=False)
        
        has_children = any([subproceedings, speeches, questions, answers])
        
        # Check if this level3_path already exists
        existing_topic = None
        for branch in branches:
            if branch.get('level') == 3 and branch.get('path') == level3_path:
                existing_topic = branch
                break
        
        # If doesn't exist, create it
        if not existing_topic:
            branches.append({
                "name": level3_name,
                "level": 3,
                "path": level3_path,
                "text": "",
                "has_children": has_children
            })
            
            # Parse subproceedings (Level 4) only for new topics
            for subproceeding in subproceedings:
                XMLParser._parse_subproceeding(subproceeding, level3_path, branches)
            
            # Parse speeches directly under topic (Level 4)
            for speech in speeches:
                XMLParser._parse_speaker(speech, level3_path, 4, branches)
            
            # Parse questions (Level 4)
            for question in questions:
                XMLParser._parse_speaker(question, level3_path, 4, branches, prefix="Question: ")
            
            # Parse answers (Level 4)
            for answer in answers:
                XMLParser._parse_speaker(answer, level3_path, 4, branches, prefix="Answer: ")
        else:
            # Update has_children if needed
            if has_children:
                existing_topic["has_children"] = True
    
    @staticmethod
    def _parse_subproceeding(
        subproceeding,
        level3_path: str,
        branches: List[Dict[str, Any]]
    ) -> None:
        """Parse a subproceeding element (Level 4)."""
        subproceedinginfo = subproceeding.find('subproceedinginfo')
        if not subproceedinginfo:
            return
        
        subproc_text_elem = subproceedinginfo.find('text')
        if not subproc_text_elem:
            return
        
        level4_name = subproc_text_elem.text.strip()
        level4_path = f"{level3_path} > {level4_name}"
        
        sub_speeches = subproceeding.find_all('speech', recursive=False)
        
        branches.append({
            "name": level4_name,
            "level": 4,
            "path": level4_path,
            "text": "",
            "has_children": len(sub_speeches) > 0
        })
        
        # Parse speakers (Level 5)
        for speech in sub_speeches:
            XMLParser._parse_speaker(speech, level4_path, 5, branches)
    
    @staticmethod
    def _parse_speaker(
        speech_elem,
        parent_path: str,
        level: int,
        branches: List[Dict[str, Any]],
        prefix: str = ""
    ) -> None:
        """Parse a speaker from a speech/question/answer element."""
        talk_start = speech_elem.find('talk.start')
        if not talk_start:
            return
        
        talker = talk_start.find('talker')
        if not talker:
            return
        
        name_elem = talker.find('name')
        if not name_elem:
            return
        
        speaker_name = name_elem.text.strip()
        if speaker_name:
            full_name = f"{prefix}{speaker_name}"
            speaker_path = f"{parent_path} > {full_name}"
            
            branches.append({
                "name": full_name,
                "level": level,
                "path": speaker_path,
                "text": "",
                "has_children": False
            })
    
    @staticmethod
    def _log_branch_summary(branches: List[Dict[str, Any]]) -> None:
        """Log summary of branches by level."""
        print(f"\n{Fore.CYAN}📊 Tree Structure Summary:{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   Total: {len(branches)} branches{Style.RESET_ALL}")
        
        level_icons = {1: '📁', 2: '📂', 3: '📄', 4: '📃', 5: '👤'}
        for level in range(1, 6):
            count = sum(1 for b in branches if b['level'] == level)
            if count > 0:
                icon = level_icons.get(level, '•')
                print(f"{Fore.CYAN}   {icon} Level {level}:{Style.RESET_ALL} {Fore.YELLOW}{count}{Style.RESET_ALL} items")
    
    @staticmethod
    def parse_fragment_content(xml_text: str) -> Dict[str, str]:
        """
        Parse XML fragment and extract all text content.
        
        Args:
            xml_text: Raw XML response text
            
        Returns:
            Dictionary mapping content keys to full text
        """
        soup = BeautifulSoup(xml_text, 'xml')
        content_map = {}
        
        # Get bill/topic name from fragment data
        bill_name = XMLParser._extract_bill_name(soup)
        
        # Get fragment text content
        fragment_text = soup.find('fragment.text')
        if not fragment_text:
            return {}
        
        body = fragment_text.find('body')
        if not body:
            return {}
        
        # Parse all paragraphs
        all_paragraphs = body.find_all('p')
        XMLParser._parse_paragraphs(
            all_paragraphs, bill_name, content_map
        )
        
        return content_map
    
    @staticmethod
    def _extract_bill_name(soup: BeautifulSoup) -> Optional[str]:
        """Extract bill/topic name from fragment data."""
        fragment_data = soup.find('fragment.data')
        if not fragment_data:
            return None
        
        topic_elem = fragment_data.find('topic')
        if not topic_elem:
            return None
        
        topicinfo = topic_elem.find('topicinfo')
        if not topicinfo:
            return None
        
        text_elem = topicinfo.find('text')
        if not text_elem:
            return None
        
        return text_elem.text.strip()
    
    @staticmethod
    def _parse_paragraphs(
        paragraphs,
        bill_name: Optional[str],
        content_map: Dict[str, str]
    ) -> None:
        """Parse paragraphs and build content map."""
        current_topic = None
        current_subproc = None
        current_speaker = None
        topic_texts = []
        subproc_texts = []
        speaker_texts = []
        
        for p in paragraphs:
            p_class = p.get('class', [])
            if isinstance(p_class, list):
                p_class = ' '.join(p_class)
            
            p_text = p.get_text(separator=' ', strip=True)
            
            # Detect topic header
            if 'SubDebate-H' in p_class:
                XMLParser._save_topic(
                    current_topic, topic_texts, bill_name, content_map
                )
                current_topic = p_text
                topic_texts = []
                current_subproc = None
                current_speaker = None
                subproc_texts = []
                speaker_texts = []
            
            # Detect subproceeding header
            elif 'SubSubDebate-H' in p_class:
                XMLParser._save_subproceeding(
                    current_subproc, subproc_texts, bill_name, 
                    current_topic, content_map
                )
                current_subproc = p_text
                subproc_texts = []
                current_speaker = None
                speaker_texts = []
            
            # Detect speaker name
            elif p.find('span', class_='MemberSpeech-H'):
                XMLParser._save_speaker(
                    current_speaker, speaker_texts, bill_name,
                    current_subproc, content_map
                )
                speaker_span = p.find('span', class_='MemberSpeech-H')
                current_speaker = speaker_span.get_text(strip=True)
                speaker_texts = [p_text]
            
            # Regular paragraph
            elif p_text:
                if current_speaker:
                    speaker_texts.append(p_text)
                if current_subproc:
                    subproc_texts.append(p_text)
                if current_topic:
                    topic_texts.append(p_text)
        
        # Save remaining sections
        XMLParser._save_speaker(
            current_speaker, speaker_texts, bill_name,
            current_subproc, content_map
        )
        XMLParser._save_subproceeding(
            current_subproc, subproc_texts, bill_name,
            current_topic, content_map
        )
        XMLParser._save_topic(
            current_topic, topic_texts, bill_name, content_map
        )
    
    @staticmethod
    def _save_topic(
        topic_name: Optional[str],
        texts: List[str],
        bill_name: Optional[str],
        content_map: Dict[str, str]
    ) -> None:
        """Save topic content to content map."""
        if topic_name and texts:
            key = f"{bill_name} > {topic_name}" if bill_name else topic_name
            content_map[key] = '\n\n'.join(texts)
    
    @staticmethod
    def _save_subproceeding(
        subproc_name: Optional[str],
        texts: List[str],
        bill_name: Optional[str],
        topic_name: Optional[str],
        content_map: Dict[str, str]
    ) -> None:
        """Save subproceeding content to content map."""
        if subproc_name and texts:
            if bill_name and topic_name:
                key = f"{bill_name} > {subproc_name}"
            elif topic_name:
                key = f"{topic_name} > {subproc_name}"
            else:
                key = subproc_name
            content_map[key] = '\n\n'.join(texts)
    
    @staticmethod
    def _save_speaker(
        speaker_name: Optional[str],
        texts: List[str],
        bill_name: Optional[str],
        subproc_name: Optional[str],
        content_map: Dict[str, str]
    ) -> None:
        """Save speaker content to content map."""
        if speaker_name and texts:
            if bill_name and subproc_name:
                key = f"{bill_name} > {subproc_name} > {speaker_name}"
            elif subproc_name:
                key = f"{subproc_name} > {speaker_name}"
            else:
                key = speaker_name
            content_map[key] = '\n\n'.join(texts)


class ContentMerger:
    """Merges content text with tree branches."""
    
    @staticmethod
    def merge_content_to_branches(
        branches: List[Dict[str, Any]],
        content_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Merge text content from content_map into branches using path matching.
        
        Args:
            branches: List of tree branch dictionaries
            content_map: Dictionary mapping content keys to text
            
        Returns:
            Updated branches list with text content
        """
        print(f"\n{Fore.CYAN}🔗 Merging content into tree structure...{Style.RESET_ALL}")
        logger.info(f"Processing {Fore.CYAN}{len(branches)}{Style.RESET_ALL} branches")
        logger.info(f"Content map: {Fore.CYAN}{len(content_map)}{Style.RESET_ALL} entries")
        
        matched = 0
        for branch in branches:
            if ContentMerger._match_content(branch, content_map):
                matched += 1
        
        with_text = sum(1 for b in branches if b.get('text'))
        print(f"{Fore.GREEN}✓ Merge complete:{Style.RESET_ALL} {Fore.YELLOW}{matched}{Style.RESET_ALL} matches, {Fore.YELLOW}{with_text}{Style.RESET_ALL} branches with text")
        
        return branches
    
    @staticmethod
    def _match_content(branch: Dict[str, Any], content_map: Dict[str, str]) -> bool:
        """
        Try to match and assign content to a branch.
        
        Returns:
            True if content was matched and assigned
        """
        name = branch['name']
        path = branch.get('path', '')
        level = branch['level']
        
        # Strategy 1: Exact path match (highest priority)
        if path in content_map:
            branch['text'] = content_map[path]
            return True
        
        # Strategy 2: Exact name match
        if name in content_map:
            branch['text'] = content_map[name]
            return True
        
        # Strategy 3: Path-based matching
        if path:
            path_parts = [p.strip() for p in path.split(' > ')]
            
            # Level 3: Bills, main topics
            if level == 3 and len(path_parts) >= 3:
                topic_name = path_parts[2]
                if topic_name in content_map:
                    branch['text'] = content_map[topic_name]
                    return True
            
            # Level 4: Subproceedings, sections
            if level == 4 and len(path_parts) >= 4:
                topic_name = path_parts[2]
                section_name = path_parts[3]
                
                patterns = [
                    f"{topic_name} > {section_name}",
                    section_name,
                ]
                
                for pattern in patterns:
                    if pattern in content_map:
                        branch['text'] = content_map[pattern]
                        return True
            
            # Level 5: Speakers
            if level == 5 and len(path_parts) >= 5:
                topic_name = path_parts[2]
                section_name = path_parts[3]
                speaker_name = path_parts[4]
                
                patterns = [
                    f"{topic_name} > {section_name} > {speaker_name}",
                    f"{section_name} > {speaker_name}",
                    speaker_name,
                ]
                
                for pattern in patterns:
                    if pattern in content_map:
                        branch['text'] = content_map[pattern]
                        return True
            
            # Fallback: fuzzy matching
            last_name = path_parts[-1] if path_parts else name
            if len(last_name) > 10:
                for content_key in content_map.keys():
                    if last_name.lower() in content_key.lower():
                        branch['text'] = content_map[content_key]
                        return True
        
        # No match found
        branch['text'] = ""
        return False


# ============================================
# MAIN SCRAPER CLASS
# ============================================

class HansardScraper:
    """
    Main scraper class for extracting Hansard parliamentary debate records
    from the NSW Parliament API.
    """
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Initialize the Hansard scraper.
        
        Args:
            timeout: Request timeout in seconds (default: 30)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
    
    def scrape(self, url: str, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrape Hansard data from a URL.
        
        Args:
            url: The Hansard URL to scrape
            output_file: Optional JSON file path to save results
            
        Returns:
            Dictionary containing all scraped data
        """
        print_header("🏛️  HANSARD NSW PARLIAMENT SCRAPER", width=80)
        print_info("URL", url, indent=2)
        if output_file:
            print_info("Output File", output_file, indent=2)
        
        # Extract document IDs
        try:
            doc_ids = DocumentIDExtractor.extract_from_url(url)
        except ValueError as e:
            logger.error(f"Error: {e}")
            return {}
        
        # Initialize result structure
        result = {
            "url": url,
            "doc_ids": doc_ids,
            "tree_branches": [],
            "contents": {},
            "full_text": ""
        }
        
        # Process each document ID
        for doc_id in doc_ids:
            print_subheader(f"📄 Processing Document: {doc_id}", width=80)
            
            try:
                # Fetch table of contents
                branches, fragment_uids = self.fetch_table_of_contents(doc_id)
                
                # Fetch all fragment contents
                content_map = self.fetch_all_fragments(fragment_uids)
                
                # Merge content into branches
                branches = ContentMerger.merge_content_to_branches(
                    branches, content_map
                )
                
                result["tree_branches"].extend(branches)
                
            except Exception as e:
                logger.error(f"Error processing {doc_id}: {e}")
                continue
        
        # Build full text
        result["full_text"] = self._build_full_text(result)
        
        # Save to file if specified
        if output_file:
            self._save_to_file(result, output_file)
        
        # Display summary
        self._display_summary(result, output_file)
        
        return result
    
    def fetch_table_of_contents(self, doc_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Fetch the Table of Contents for a document.
        
        Args:
            doc_id: The document ID
            
        Returns:
            Tuple of (branches list, fragment_uids dict)
        """
        print(f"\n{Fore.CYAN}📥 Fetching Table of Contents...{Style.RESET_ALL}")
        
        url = f"{API_BASE_URL}/daily/tableofcontents/{doc_id}"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"Response: {Fore.GREEN}✓ Success{Style.RESET_ALL} (Status: {response.status_code})")
            
            branches, fragment_uids = XMLParser.parse_table_of_contents(response.text)
            
            return branches, fragment_uids
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching TOC: {e}")
            return [], {}
    
    def fetch_all_fragments(self, fragment_uids: Dict[str, str]) -> Dict[str, str]:
        """
        Fetch content from multiple fragment UIDs.
        
        Args:
            fragment_uids: Dictionary mapping topic paths to fragment UIDs
            
        Returns:
            Dictionary mapping content keys to full text
        """
        print(f"\n{Fore.CYAN}📦 Fetching fragment contents...{Style.RESET_ALL}")
        print(f"{Fore.WHITE}   Total fragments: {Fore.CYAN}{len(fragment_uids)}{Style.RESET_ALL}\n")
        
        all_content = {}
        successful = 0
        failed = 0
        total = len(fragment_uids)
        
        for topic_path, uid in fragment_uids.items():
            try:
                url = f"{API_BASE_URL}/daily/fragment/{uid}"
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                content_map = XMLParser.parse_fragment_content(response.text)
                
                # Store content using the full path as key
                for content_key, content_text in content_map.items():
                    # Use both the fragment key and path-based keys
                    all_content[topic_path] = content_text
                    all_content[content_key] = content_text
                
                successful += 1
                
                # Display topic name (last part of path)
                display_name = topic_path.split(' > ')[-1] if ' > ' in topic_path else topic_path
                print_progress(
                    successful, 
                    total, 
                    display_name, 
                    f"{len(content_map)} items"
                )
                
            except Exception as e:
                failed += 1
                display_name = topic_path.split(' > ')[-1] if ' > ' in topic_path else topic_path
                print(f"{Fore.RED}  ✗ Failed: {display_name[:50]}... - {e}{Style.RESET_ALL}")
                continue
        
        print(f"\n{Fore.GREEN}✓ Fetch complete:{Style.RESET_ALL} {Fore.YELLOW}{successful}{Style.RESET_ALL} successful, {Fore.RED}{failed}{Style.RESET_ALL} failed")
        logger.info(f"Total content items: {Fore.CYAN}{len(all_content)}{Style.RESET_ALL}")
        
        return all_content
    
    def _build_full_text(self, data: Dict[str, Any]) -> str:
        """
        Build full text from all scraped data.
        
        Args:
            data: Dictionary containing all scraped data
            
        Returns:
            Full text as a string
        """
        print(f"\n{Fore.CYAN}📝 Building full text...{Style.RESET_ALL}")
        
        text_parts = []
        
        # Add tree branches
        if "tree_branches" in data:
            text_parts.append("=== TREE BRANCHES ===")
            for branch in data["tree_branches"]:
                if isinstance(branch, dict):
                    level = branch.get('level', 0)
                    path = branch.get('path', branch.get('name', ''))
                    text_parts.append(f"[Level {level}] {path}")
            text_parts.append("")
        
        full_text = "\n".join(text_parts)
        logger.info(f"Text size: {Fore.CYAN}{len(full_text):,}{Style.RESET_ALL} characters")
        
        return full_text
    
    def _save_to_file(self, data: Dict[str, Any], output_file: str) -> None:
        """Save scraped data to a JSON file."""
        print(f"\n{Fore.CYAN}💾 Saving results...{Style.RESET_ALL}")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"File saved: {Fore.GREEN}{output_file}{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"Error saving file: {e}")
    
    def _display_summary(self, data: Dict[str, Any], output_file: Optional[str]) -> None:
        """Display a summary of the scraping results."""
        print_header("✅ SCRAPING COMPLETED!", width=80)
        
        print(f"{Fore.CYAN}📊 Summary:{Style.RESET_ALL}\n")
        print_info("Document IDs", len(data['doc_ids']), indent=2)
        print_info("Tree Branches", len(data['tree_branches']), indent=2)
        
        # Count branches with text
        with_text = sum(1 for b in data['tree_branches'] if b.get('text'))
        print_info("Branches with Content", with_text, indent=2)
        
        if output_file:
            print_info("Output File", output_file, indent=2)
        
        print(f"\n{Fore.GREEN}{Style.BRIGHT}🎉 All tasks completed successfully!{Style.RESET_ALL}\n")


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Main entry point for the script."""
    
    print(f"\n{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}{'🏛️  HANSARD NSW PARLIAMENT - API SCRAPER'.center(70)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}\n")
    
    target_url = input(f"{Fore.CYAN}📝 Input target URL:{Style.RESET_ALL} ")
    
    try:
        # Initialize scraper
        scraper = HansardScraper()
        
        # Start scraping
        print(f"\n{Fore.GREEN}🚀 Starting data scraping...{Style.RESET_ALL}")
        result = scraper.scrape(target_url, "hansard_scraped.json")
        
        if result:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✅ Scraping successful!{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.YELLOW}⚠️  Scraping completed but no data retrieved{Style.RESET_ALL}\n")
            
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}⚠️  Program cancelled by user{Style.RESET_ALL}\n")
    except Exception as e:
        print(f"\n\n{Fore.RED}✗ Fatal error: {e}{Style.RESET_ALL}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
