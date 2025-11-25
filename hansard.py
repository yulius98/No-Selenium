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
from colorama import init, Fore, Back, Style
from dataclasses import dataclass
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
            "text": "",  # Level 1 should have empty text
            "has_children": True,
            "uid": None  # Level 1 has no UID
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
        
        # Always create level 2 even if there are no topics
        has_children = len(topics) > 0
        
        # Check if this level2_path already exists
        # Remove the deduplication to allow duplicate Level 2 branches with the same path
        # existing_branch = None
        # for branch in branches:
        #     if branch.get('level') == 2 and branch.get('path') == level2_path:
        #         existing_branch = branch
        #         break
        
        # Always append a new Level 2 branch for each proceeding (allow duplicates)
        branches.append({
            "name": level2_name,
            "level": 2,
            "path": level2_path,
            "text": "",  # Level 2 should have empty text
            "has_children": has_children,
            "uid": None  # Level 2 has no UID
        })
        
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
            # Log UID information
            logger.info(f"🔗 UID found for: {Fore.CYAN}{level3_name}{Style.RESET_ALL} → {Fore.YELLOW}{topic_uid}{Style.RESET_ALL}")
        
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
                "text": "",  # Level 3 will get content later from ContentMerger
                "has_children": has_children,
                "uid": topic_uid  # Store the UID for Level 3
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
            "text": "",  # Level 4 should have empty text
            "has_children": len(sub_speeches) > 0,
            "uid": None  # Level 4 has no UID
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
                "text": "",  # Speaker level (5) should have empty text
                "has_children": False,
                "uid": None  # Level 5 has no UID
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
    def _log_uid_summary(branches: List[Dict[str, Any]], fragment_uids: Dict[str, str]) -> None:
        """Log summary of UIDs found in the data."""
        print(f"\n{Fore.MAGENTA}🔗 UID Summary:{Style.RESET_ALL}")
        
        # Count branches with UIDs
        branches_with_uid = [b for b in branches if b.get('uid')]
        print(f"{Fore.GREEN}   Branches with UID: {len(branches_with_uid)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   Total Fragment UIDs: {len(fragment_uids)}{Style.RESET_ALL}")
        
        # Display each UID
        for branch in branches_with_uid:
            uid = branch.get('uid')
            name = branch.get('name', 'Unknown')
            level = branch.get('level', 0)
            print(f"{Fore.CYAN}   📎 Level {level}:{Style.RESET_ALL} {Fore.WHITE}{name[:50]}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}      UID: {uid}{Style.RESET_ALL}")
        
        if not branches_with_uid:
            print(f"{Fore.YELLOW}   No UIDs found in branches{Style.RESET_ALL}")
    
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
        
        # Extract complete content from the entire fragment
        if bill_name:
            # Get all text content from the fragment
            complete_content = XMLParser._extract_complete_fragment_text(body)
            if complete_content:
                content_map[bill_name] = complete_content
        
        # Parse all paragraphs for detailed content mapping
        all_paragraphs = body.find_all('p')
        XMLParser._parse_paragraphs(
            all_paragraphs, bill_name, content_map
        )
        
        return content_map
    
    @staticmethod
    def _extract_complete_fragment_text(body) -> str:
        """Extract complete text from the entire fragment body."""
        all_content = []
        
        # Get all paragraphs in order
        paragraphs = body.find_all('p')
        
        for p in paragraphs:
            p_class = p.get('class', [])
            if isinstance(p_class, list):
                p_class = ' '.join(p_class)
            
            p_text = p.get_text(separator=' ', strip=True)
            if p_text:
                # Format headers nicely
                if any(header_class in p_class for header_class in ['SubDebate-H', 'SubSubDebate-H']):
                    all_content.append(f"\n{p_text}\n")
                elif p.find('span', class_='MemberSpeech-H'):
                    # Extract speaker name and format it
                    speaker_span = p.find('span', class_='MemberSpeech-H')
                    speaker_name = speaker_span.get_text(strip=True)
                    all_content.append(f"\n{speaker_name}\n")
                    # Add any additional text in the paragraph
                    remaining_text = p_text.replace(speaker_name, '').strip()
                    if remaining_text:
                        all_content.append(remaining_text)
                else:
                    all_content.append(p_text)
        
        return '\n\n'.join(filter(None, all_content))
    
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
        # Collect all text for the main topic (Level 3)
        all_topic_text = []
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
            
            # Add all text to main topic collection
            if p_text:
                all_topic_text.append(p_text)
            
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
        
        # Save complete topic content using bill name as key (for Level 3 matching)
        if bill_name and all_topic_text:
            content_map[bill_name] = '\n\n'.join(all_topic_text)
    
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
        Merge text content from content_map into branches using UID and path matching.
        
        Args:
            branches: List of tree branch dictionaries
            content_map: Dictionary mapping content keys to text
            
        Returns:
            Updated branches list with text content
        """
        print(f"\n{Fore.CYAN}🔗 Merging content into tree structure...{Style.RESET_ALL}")
        logger.info(f"Processing {Fore.CYAN}{len(branches)}{Style.RESET_ALL} branches")
        logger.info(f"Content map: {Fore.CYAN}{len(content_map)}{Style.RESET_ALL} entries")
        
        # Extract UID mappings if available
        uid_mappings = content_map.get('_uid_mappings', {})
        
        matched = 0
        uid_matches = 0
        fallback_matches = 0
        
        for branch in branches:
            if branch['level'] == 3:  # Only process Level 3 branches
                uid = branch.get('uid')
                name = branch.get('name', '')
                
                if ContentMerger._match_content(branch, content_map, uid_mappings):
                    matched += 1
                    if uid and uid_mappings and uid in uid_mappings:
                        uid_matches += 1
                    else:
                        fallback_matches += 1
        
        with_text = sum(1 for b in branches if b.get('text'))
        print(f"{Fore.GREEN}✓ Merge complete:{Style.RESET_ALL} {Fore.YELLOW}{matched}{Style.RESET_ALL} matches, {Fore.YELLOW}{with_text}{Style.RESET_ALL} branches with text")
        
        return branches
    
    @staticmethod
    def _match_content(branch: Dict[str, Any], content_map: Dict[str, str], uid_mappings: Dict[str, str] = None) -> bool:
        """
        Try to match and assign content to a branch.
        Only Level 3 branches will get text content.
        
        Returns:
            True if content was matched and assigned
        """
        name = branch['name']
        path = branch.get('path', '')
        level = branch['level']
        uid = branch.get('uid')
        
        # Only Level 3 branches should have text content
        # Levels 1, 2, 4, and 5 should have empty text
        if level != 3:
            branch['text'] = ""
            return False
        
        # Strategy 1: Direct UID match (ABSOLUTE HIGHEST PRIORITY)
        # If UID exists and has content, use it exclusively - no fallback to other strategies
        if uid and uid_mappings and uid in uid_mappings:
            content = uid_mappings[uid]
            if content and len(content.strip()) > 0:
                branch['text'] = content
                return True
        
        # Strategy 2: Exact path match (only if no UID or UID failed)
        if path in content_map:
            content = content_map[path]
            if content and len(content.strip()) > 0:
                branch['text'] = content
                return True
        
        # Strategy 3: Exact name match (only if no UID or UID failed)
        if name in content_map:
            content = content_map[name]
            if content and len(content.strip()) > 0:
                branch['text'] = content
                return True
        
        # Strategy 4: Construct bill content for bills (only if no UID or UID failed)
        if 'Bill 2025' in name:
            complete_content = ContentMerger._construct_bill_content(name, content_map, path, uid_mappings, exclude_uid=uid)
            if complete_content and len(complete_content.strip()) > 0:
                branch['text'] = complete_content
                return True
        
        # Strategy 5: Path-based matching for Level 3
        if path:
            path_parts = [p.strip() for p in path.split(' > ')]
            if len(path_parts) >= 3:
                topic_name = path_parts[2]
                if topic_name in content_map:
                    content = content_map[topic_name]
                    if content and len(content.strip()) > 0:
                        branch['text'] = content
                        return True
        
        # Strategy 6: Try partial matching for complex names
        if name and len(name) > 20:
            best_match = None
            best_score = 0
            
            for content_key, content_text in content_map.items():
                if content_key == '_uid_mappings':  # Skip the special UID mappings key
                    continue
                    
                score = 0
                # Exact match
                if content_key == name:
                    score = 100
                # Partial matches
                elif name.lower() in content_key.lower():
                    score = 80
                elif content_key.lower() in name.lower():
                    score = 70
                # Content quality indicators
                if content_text and len(content_text) > 1000:
                    score += 10
                if name in content_text:
                    score += 15
                
                if score > best_score and content_text and len(content_text.strip()) > 0:
                    best_score = score
                    best_match = content_text
            
            if best_match and best_score > 50:  # Minimum threshold
                branch['text'] = best_match
                return True
        
        # No match found for Level 3
        branch['text'] = ""
        return False
    
    @staticmethod
    def _construct_bill_content(bill_name: str, content_map: Dict[str, str], bill_path: str, uid_mappings: Dict[str, str] = None, exclude_uid: str = None) -> str:
        """
        Construct complete bill content by finding the best matching content from the API fragments.
        Uses UID mappings first, then falls back to flexible matching based on bill name and path.
        
        Args:
            exclude_uid: UID to exclude from consideration to prevent conflicts with direct UID matching
        """
        # Constructing bill content with UID exclusion
        
        # Find the best matching content using flexible matching
        best_content = None
        best_score = 0
        
        # Check all content sources
        all_content = dict(content_map)  # Copy to avoid modifying original
        if uid_mappings:
            # Add UID mappings but exclude the specific UID to prevent conflicts
            for uid_key, uid_content in uid_mappings.items():
                if exclude_uid and uid_key == exclude_uid:
                    continue
                all_content[uid_key] = uid_content
        
        for content_key, content_text in all_content.items():
            if content_key == '_uid_mappings':  # Skip the special UID mappings key
                continue
            if exclude_uid and content_key == exclude_uid:  # Skip excluded UID
                continue
                
            if not content_text or len(content_text.strip()) == 0:
                continue
                
            score = 0
            
            # Score based on exact name match
            if bill_name == content_key:
                score += 100
            
            # Score based on partial name match
            elif bill_name.lower() in content_key.lower():
                score += 80
            elif content_key.lower() in bill_name.lower():
                score += 70
            
            # Score based on path match
            elif bill_path and bill_path in content_key:
                score += 60
            
            # Score based on content length (prefer more complete content)
            if len(content_text) > 1000:
                score += 10
            
            # Score based on content quality indicators
            if "Second Reading Speech" in content_text:
                score += 20
            if bill_name in content_text:
                score += 15
            if "Bill 2025" in content_text:
                score += 10
            
            # Select the highest scoring content
            if score > best_score:
                best_score = score
                best_content = content_text
                logger.info(f"  New best match: {content_key[:50]}... (score: {score})")
        
        # Return the best matching content or empty string if nothing found
        result = best_content if best_content and best_score > 30 else ""
        logger.info(f"  Final result: {len(result)} chars (score: {best_score})")
        return result


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
        
        max_retries = 3
        backoff_factor = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                logger.info(f"Response: {Fore.GREEN}✓ Success{Style.RESET_ALL} (Status: {response.status_code})")
                
                branches, fragment_uids = XMLParser.parse_table_of_contents(response.text)
                
                return branches, fragment_uids
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching TOC (Attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    wait_time = backoff_factor ** (attempt - 1)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached. Failed to fetch Table of Contents for document ID: {doc_id}")
        
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
        
        max_retries = 3
        backoff_factor = 2
        
        all_content = {}
        uid_to_content = {}  # Direct UID to content mapping
        successful = 0
        failed = 0
        total = len(fragment_uids)
        
        for topic_path, uid in fragment_uids.items():
            for attempt in range(1, max_retries + 1):
                try:
                    url = f"{API_BASE_URL}/daily/fragment/{uid}"
                    response = self.session.get(url, timeout=self.timeout)
                    response.raise_for_status()
                    
                    content_map = XMLParser.parse_fragment_content(response.text)
                    
                    # Log the fetched content for debugging
                    logger.info(f"Fetched fragment UID {uid}: {len(content_map)} content items")
                    
                    # Store content using multiple keys for better matching
                    for content_key, content_text in content_map.items():
                        # Store with topic path as primary key
                        all_content[topic_path] = content_text
                        # Store with UID as key for direct matching
                        uid_to_content[uid] = content_text
                        # Store with content key for fallback matching
                        all_content[content_key] = content_text
                        
                        # Also store with topic name only (last part of path)
                        topic_name = topic_path.split(' > ')[-1] if ' > ' in topic_path else topic_path
                        all_content[topic_name] = content_text
                        
                        logger.info(f"  Content stored for: {content_key} (Length: {len(content_text)} chars)")
                    
                    successful += 1
                    
                    # Display topic name (last part of path)
                    display_name = topic_path.split(' > ')[-1] if ' > ' in topic_path else topic_path
                    print_progress(
                        successful, 
                        total, 
                        display_name, 
                        f"{len(content_map)} items"
                    )
                    
                    break  # Success, break retry loop
                except Exception as e:
                    if attempt < max_retries:
                        wait_time = backoff_factor ** (attempt - 1)
                        logger.error(f"Error fetching fragment UID {uid} (Attempt {attempt}/{max_retries}): {e}")
                        logger.info(f"Retrying in {wait_time} seconds...")
                        import time
                        time.sleep(wait_time)
                    else:
                        failed += 1
                        display_name = topic_path.split(' > ')[-1] if ' > ' in topic_path else topic_path
                        print(f"{Fore.RED}  ✗ Failed: {display_name[:50]}... - {e}{Style.RESET_ALL}")
                        break
        
        print(f"\n{Fore.GREEN}✓ Fetch complete:{Style.RESET_ALL} {Fore.YELLOW}{successful}{Style.RESET_ALL} successful, {Fore.RED}{failed}{Style.RESET_ALL} failed")
        logger.info(f"Total content items: {Fore.CYAN}{len(all_content)}{Style.RESET_ALL}")
        logger.info(f"UID to content mappings: {Fore.CYAN}{len(uid_to_content)}{Style.RESET_ALL}")
        
        # Store UID mappings in all_content for use by ContentMerger
        all_content['_uid_mappings'] = uid_to_content
        
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


def update_uid_content(json_file_path: str, uid: str) -> None:
    """
    Update content for a specific UID by fetching directly from the fragment API.
    
    Args:
        json_file_path: Path to the JSON file to update
        uid: The UID to update
    """
    print_header(f"🔄 UPDATING UID CONTENT: {uid}", width=80)
    
    try:
        # Load current JSON
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        
        # Get content from fragment API
        fragment_url = f'https://api.parliament.nsw.gov.au/api/hansard/search/daily/fragment/{uid}'
        print(f"{Fore.CYAN}📡 Fetching content from API...{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}URL: {fragment_url}{Style.RESET_ALL}")
        
        response = requests.get(fragment_url)
        
        if response.status_code == 200:
            print(f"{Fore.GREEN}✓ API response successful{Style.RESET_ALL}")
            
            soup = BeautifulSoup(response.text, 'xml')
            
            # Extract text content using the same method as the scraper
            body = soup.find('body')
            if body:
                text_content = []
                for p in body.find_all('p'):
                    p_text = p.get_text(strip=True)
                    if p_text:
                        text_content.append(p_text)
                
                correct_text = '\n\n'.join(text_content)
                
                print(f"{Fore.GREEN}✓ Extracted {len(correct_text)} characters{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Preview: {correct_text[:100]}...{Style.RESET_ALL}")
                
                # Find and update the branch with this UID
                updated = False
                for branch in data.get('tree_branches', []):
                    if branch.get('uid') == uid:
                        old_text = branch.get('text', '')
                        branch['text'] = correct_text
                        
                        print(f"\n{Fore.GREEN}✓ Updated branch: {branch['name']}{Style.RESET_ALL}")
                        print(f"{Fore.YELLOW}Old text length: {len(old_text)} chars{Style.RESET_ALL}")
                        print(f"{Fore.CYAN}New text length: {len(correct_text)} chars{Style.RESET_ALL}")
                        
                        if old_text != correct_text:
                            print(f"{Fore.GREEN}✓ Content changed - update needed{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.YELLOW}ℹ Content identical - no changes needed{Style.RESET_ALL}")
                        
                        updated = True
                        break
                
                if updated:
                    # Save updated JSON
                    with open(json_file_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"\n{Fore.GREEN}✅ JSON file updated successfully!{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.RED}✗ UID {uid} not found in JSON file{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ No body content found in API response{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ API request failed: HTTP {response.status_code}{Style.RESET_ALL}")
            
    except FileNotFoundError:
        print(f"{Fore.RED}✗ JSON file not found: {json_file_path}{Style.RESET_ALL}")
    except json.JSONDecodeError:
        print(f"{Fore.RED}✗ Invalid JSON file: {json_file_path}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✗ Error updating UID: {e}{Style.RESET_ALL}")


def display_uids_from_json(json_file_path: str):
    """
    Load and display UIDs from an existing JSON file.
    
    Args:
        json_file_path: Path to the JSON file containing Hansard data
    """
    print_header("🔍 UID ANALYSIS FROM JSON", width=80)
    print_info("JSON File", json_file_path, indent=2)
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print_subheader("📊 JSON Data Analysis", width=80)
        
        if 'tree_branches' in data:
            branches = data['tree_branches']
            print_info("Total Branches", len(branches), indent=2)
            
            # Analyze UIDs
            branches_with_uid = []
            branches_without_uid = []
            
            for branch in branches:
                if branch.get('uid'):
                    branches_with_uid.append(branch)
                else:
                    branches_without_uid.append(branch)
            
            print_info("Branches with UID", len(branches_with_uid), indent=2)
            print_info("Branches without UID", len(branches_without_uid), indent=2)
            
            # Display all UIDs
            if branches_with_uid:
                print_subheader("🔗 UID Details", width=80)
                
                for i, branch in enumerate(branches_with_uid, 1):
                    uid = branch.get('uid')
                    name = branch.get('name', 'Unknown')
                    level = branch.get('level', 0)
                    path = branch.get('path', '')
                    
                    print(f"\n{Fore.CYAN}#{i} - Level {level} Branch:{Style.RESET_ALL}")
                    print_info("Name", name, indent=4)
                    print_info("UID", uid, indent=4)
                    print_info("Path", path, indent=4)
                    
                    if len(name) > 50:
                        print(f"{Fore.YELLOW}    📝 (Long name truncated for display){Style.RESET_ALL}")
            
            else:
                print(f"\n{Fore.YELLOW}⚠️  No UIDs found in the JSON data{Style.RESET_ALL}")
                print(f"{Fore.CYAN}💡 This might be an older format. Run the scraper again to generate UIDs.{Style.RESET_ALL}")
        
        else:
            print(f"{Fore.RED}✗ No 'tree_branches' found in JSON file{Style.RESET_ALL}")
    
    except FileNotFoundError:
        logger.error(f"File not found: {json_file_path}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON file: {json_file_path}")
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}")


if __name__ == "__main__":
    # Check if user wants to analyze existing JSON or update specific UID
    if len(sys.argv) > 1:
        if sys.argv[1] == "--analyze-json" and len(sys.argv) > 2:
            display_uids_from_json(sys.argv[2])
        elif sys.argv[1] == "--update-uid" and len(sys.argv) > 3:
            update_uid_content(sys.argv[2], sys.argv[3])
        elif sys.argv[1] == "--help":
            print_header("🏛️  HANSARD NSW PARLIAMENT SCRAPER - HELP", width=80)
            print(f"{Fore.CYAN}Usage:{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}python hansard.py{Style.RESET_ALL}                          - Run interactive scraper")
            print(f"  {Fore.WHITE}python hansard.py --analyze-json <file>{Style.RESET_ALL}      - Analyze existing JSON file")
            print(f"  {Fore.WHITE}python hansard.py --update-uid <file> <uid>{Style.RESET_ALL} - Update specific UID content")
            print(f"  {Fore.WHITE}python hansard.py --help{Style.RESET_ALL}                    - Show this help message")
            print(f"\n{Fore.CYAN}Examples:{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}python hansard.py --analyze-json hansard_scraped.json{Style.RESET_ALL}")
            print(f"  {Fore.WHITE}python hansard.py --update-uid hansard_scraped.json HANSARD-1323879322-160369{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Unknown argument: {sys.argv[1]}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Use --help for usage information{Style.RESET_ALL}")
    else:
        main()
