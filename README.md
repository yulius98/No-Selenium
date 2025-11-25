# Hansard NSW Parliament Scraper

A lightweight, efficient web scraper for extracting Hansard (parliamentary debate records) data from the NSW Parliament website using their official API.

## 🌟 Key Features

- **API-Based Scraping**: Direct API calls instead of browser automation
- **Fast & Reliable**: No browser overhead, faster execution
- **Structured Data**: Hierarchical tree structure with 5 levels
- **Complete Content**: Extracts debates, speeches, questions, and answers
- **Clean Architecture**: Object-oriented design with reusable components
- **Type-Safe**: Full type hints for better code quality
- **Robust Error Handling**: Comprehensive logging and error management

## 📋 Table of Contents

- [Why API Over Selenium?](#why-api-over-selenium)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Application Flow](#application-flow)
- [Architecture](#architecture)
- [Usage Examples](#usage-examples)
- [Output Format](#output-format)
- [Contributing](#contributing)

## 🚀 Why API Over Selenium?

This scraper uses the NSW Parliament's official API instead of Selenium for several compelling reasons:

### Performance Advantages

| Feature | API-Based | Selenium-Based |
|---------|-----------|----------------|
| Speed | ⚡ **Fast** (2-5 seconds) | 🐌 Slow (30-60 seconds) |
| Memory Usage | 📉 **Low** (~50MB) | 📈 High (~500MB+) |
| CPU Usage | 💚 **Minimal** | 🔴 Significant |
| Reliability | ✅ **Very High** | ⚠️ Moderate |
| Setup Complexity | 🟢 **Simple** | 🟡 Complex |

### Detailed Comparison

#### 1. **Performance**
- **API**: Direct HTTP requests return data in milliseconds
- **Selenium**: Launches full browser, loads JavaScript, renders DOM (10-20x slower)

#### 2. **Resource Efficiency**
- **API**: Minimal memory footprint, single Python process
- **Selenium**: Requires ChromeDriver/GeckoDriver, browser instance, significant RAM

#### 3. **Reliability**
- **API**: No dependency on browser versions, DOM changes, or JavaScript execution
- **Selenium**: Prone to timeouts, element not found errors, version compatibility issues

#### 4. **Scalability**
- **API**: Easy to parallelize, can handle hundreds of concurrent requests
- **Selenium**: Limited by browser instances, difficult to scale

#### 5. **Maintenance**
- **API**: Stable API endpoints, minimal breaking changes
- **Selenium**: Frequent updates needed for browser/driver compatibility

#### 6. **Development Experience**
- **API**: Simple debugging with requests library
- **Selenium**: Complex debugging of browser interactions, waits, and selectors

#### 7. **Deployment**
- **API**: Works in any environment, including serverless
- **Selenium**: Requires full OS with browser support

### When to Use Selenium Instead?

Use Selenium only when:
- Content is generated entirely by JavaScript (not the case here)
- API endpoints are not available or documented
- Need to interact with complex forms or authentication
- Need to capture screenshots or visual testing

## 📦 Installation

### Requirements

- Python 3.7+
- pip (Python package manager)

### Step 1: Clone or Download

```bash
git clone <repository-url>
cd hansard-scraper
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually install:

```bash
pip install requests beautifulsoup4 lxml
```

### Optional: Playwright (for browser preview)

```bash
pip install playwright
playwright install chromium
```

## ⚡ Quick Start

### Basic Usage

```python
from hansard_refactored import HansardScraper

# Initialize scraper
scraper = HansardScraper()

# Scrape data from URL
url = "https://www.parliament.nsw.gov.au/Hansard/Pages/HansardFull.aspx#/..."
result = scraper.scrape(url, output_file="hansard_data.json")

print(f"Scraped {len(result['tree_branches'])} tree branches")
```

### Command Line

```bash
python hansard_refactored.py
```

The script will scrape the default URL and save results to `hansard_scraped.json`.

## 🔄 Application Flow

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER INPUT                          │
│                     (Hansard URL)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 1: Extract Document IDs                   │
│           (DocumentIDExtractor.extract_from_url)           │
│                                                             │
│  Input:  URL with HANSARD-XXXXXX-XXXXXX                   │
│  Output: ['HANSARD-1323879322-160369']                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         STEP 2: Fetch Table of Contents (TOC)              │
│          (HansardScraper.fetch_table_of_contents)          │
│                                                             │
│  API: /daily/tableofcontents/{doc_id}                      │
│  Returns: XML with hierarchical structure                  │
│                                                             │
│  Process:                                                   │
│  ├─ Parse XML metadata (date, house)                       │
│  ├─ Extract proceedings → topics → speeches                │
│  ├─ Build 5-level tree structure                           │
│  └─ Collect fragment UIDs for content fetching             │
│                                                             │
│  Output:                                                    │
│  ├─ branches: List of tree nodes (Levels 1-5)              │
│  └─ fragment_uids: Dict {topic_name: uid}                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           STEP 3: Fetch Fragment Contents                  │
│         (HansardScraper.fetch_all_fragments)               │
│                                                             │
│  For each fragment UID:                                     │
│    API: /daily/fragment/{uid}                              │
│    Returns: XML with full debate text                      │
│                                                             │
│  Process (XMLParser.parse_fragment_content):               │
│  ├─ Extract bill/topic name                                │
│  ├─ Parse paragraphs with class indicators                 │
│  ├─ Identify sections, subsections, speakers               │
│  └─ Build content map {path: text}                         │
│                                                             │
│  Output: content_map Dict {content_key: full_text}         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         STEP 4: Merge Content with Tree Branches           │
│        (ContentMerger.merge_content_to_branches)           │
│                                                             │
│  Process:                                                   │
│  ├─ For each branch in tree structure                      │
│  ├─ Match with content_map using:                          │
│  │  ├─ Exact name match                                    │
│  │  ├─ Path-based matching                                 │
│  │  └─ Fuzzy matching                                      │
│  └─ Assign matched text to branch                          │
│                                                             │
│  Output: Enhanced branches with text content               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 5: Build Full Text                       │
│            (HansardScraper._build_full_text)               │
│                                                             │
│  Combines all tree paths and content into                  │
│  a single formatted text document                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 6: Save to JSON File                     │
│           (HansardScraper._save_to_file)                   │
│                                                             │
│  Output: hansard_scraped.json                              │
│  {                                                          │
│    "url": "...",                                           │
│    "doc_ids": [...],                                       │
│    "tree_branches": [...],                                 │
│    "full_text": "..."                                      │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Flow Description

#### Phase 1: URL Processing
1. User provides Hansard URL
2. `DocumentIDExtractor` uses regex to find `HANSARD-XXXXXX-XXXXXX` patterns
3. Extracts the last (most specific) document ID

#### Phase 2: Structure Extraction
1. Makes API call to `/daily/tableofcontents/{doc_id}`
2. Receives XML with parliamentary session structure
3. `XMLParser.parse_table_of_contents` extracts:
   - **Level 1**: House and Date (e.g., "Legislative Assembly (2024-11-20)")
   - **Level 2**: Proceedings (e.g., "Bills", "Motions", "Question Time")
   - **Level 3**: Topics (e.g., "Education Amendment Bill 2024")
   - **Level 4**: Subsections or Speakers
   - **Level 5**: Individual speakers (in nested debates)

#### Phase 3: Content Retrieval
1. For each fragment UID collected in Phase 2
2. Makes API call to `/daily/fragment/{uid}`
3. Receives XML with full debate text
4. `XMLParser.parse_fragment_content` extracts:
   - Paragraph-level content
   - Speaker attributions
   - Section hierarchies

#### Phase 4: Content Integration
1. `ContentMerger` matches content to tree nodes
2. Uses multiple strategies:
   - Direct name matching
   - Path-based hierarchical matching
   - Fuzzy substring matching
3. Ensures each tree node gets appropriate content

#### Phase 5: Output Generation
1. Builds comprehensive full text
2. Serializes to JSON with all metadata
3. Provides summary statistics

## 🏗️ Architecture

### Class Structure

```
hansard_refactored.py
│
├── BrowserPreview
│   └── open_url()              # Optional browser preview
│
├── DocumentIDExtractor
│   └── extract_from_url()      # Regex-based ID extraction
│
├── XMLParser
│   ├── parse_table_of_contents()
│   ├── parse_fragment_content()
│   └── [private helper methods]
│
├── ContentMerger
│   └── merge_content_to_branches()
│
└── HansardScraper              # Main orchestrator
    ├── scrape()
    ├── fetch_table_of_contents()
    ├── fetch_all_fragments()
    └── [private helper methods]
```

### Design Principles

1. **Single Responsibility**: Each class has one clear purpose
2. **Separation of Concerns**: Parsing, merging, and scraping are separate
3. **Reusability**: Components can be used independently
4. **Type Safety**: Full type hints throughout
5. **Testability**: Static methods enable easy unit testing

### Key Components

#### HansardScraper
- **Purpose**: Main orchestrator for scraping workflow
- **Responsibilities**: 
  - Manage HTTP session
  - Coordinate scraping phases
  - Handle file I/O
  - Provide user feedback

#### XMLParser
- **Purpose**: Parse XML responses from API
- **Responsibilities**:
  - Extract metadata from headers
  - Build hierarchical tree structure
  - Parse content paragraphs
  - Map speakers to text

#### ContentMerger
- **Purpose**: Match content to tree structure
- **Responsibilities**:
  - Implement matching strategies
  - Handle edge cases
  - Ensure data completeness

## 💡 Usage Examples

### Example 1: Basic Scraping

```python
from hansard_refactored import HansardScraper

scraper = HansardScraper()
url = "https://www.parliament.nsw.gov.au/Hansard/..."
result = scraper.scrape(url, output_file="output.json")
```

### Example 2: Custom Timeout

```python
from hansard_refactored import HansardScraper

# Set 60-second timeout for slow connections
scraper = HansardScraper(timeout=60)
result = scraper.scrape(url)
```

### Example 3: Process Multiple URLs

```python
from hansard_refactored import HansardScraper

urls = [
    "https://www.parliament.nsw.gov.au/...",
    "https://www.parliament.nsw.gov.au/...",
]

scraper = HansardScraper()
for i, url in enumerate(urls):
    result = scraper.scrape(url, output_file=f"hansard_{i}.json")
```

### Example 4: Extract Specific Content

```python
from hansard_refactored import HansardScraper

scraper = HansardScraper()
result = scraper.scrape(url)

# Get all Level 3 branches (main topics)
topics = [b for b in result['tree_branches'] if b['level'] == 3]

for topic in topics:
    print(f"{topic['name']}: {len(topic['text'])} characters")
```

### Example 5: Browser Preview (Optional)

```python
from hansard_refactored import BrowserPreview

# Open URL in browser to verify content
url = "https://www.parliament.nsw.gov.au/Hansard/..."
BrowserPreview.open_url(url, headless=False)
```

## 📄 Output Format

### JSON Structure

```json
{
  "url": "https://www.parliament.nsw.gov.au/...",
  "doc_ids": ["HANSARD-1323879322-160369"],
  "tree_branches": [
    {
      "name": "Legislative Assembly (2024-11-20)",
      "level": 1,
      "path": "Legislative Assembly (2024-11-20)",
      "text": "",
      "has_children": true
    },
    {
      "name": "Bills",
      "level": 2,
      "path": "Legislative Assembly (2024-11-20) > Bills",
      "text": "",
      "has_children": true
    },
    {
      "name": "Education Amendment Bill 2024",
      "level": 3,
      "path": "Legislative Assembly (2024-11-20) > Bills > Education Amendment Bill 2024",
      "text": "Full debate text...",
      "has_children": true
    }
  ],
  "full_text": "Concatenated text of all branches..."
}
```

### Tree Level Hierarchy

1. **Level 1**: Parliamentary House and Date
   - Example: `"Legislative Assembly (2024-11-20)"`

2. **Level 2**: Main Proceeding Types
   - Examples: `"Bills"`, `"Motions"`, `"Question Time"`

3. **Level 3**: Specific Topics/Bills
   - Examples: `"Education Amendment Bill 2024"`, `"Budget Estimates"`

4. **Level 4**: Subsections or Primary Speakers
   - Examples: `"Second Reading"`, `"Hon. John Smith MP"`

5. **Level 5**: Individual Speakers in Subsections
   - Examples: Speaker names within specific debate sections

## 🛠️ Development

### Project Structure

```
hansard-scraper/
├── hansard_refactored.py    # Main refactored script
├── hansard.py               # Original script (for reference)
├── README.md                # This file
├── README_ARCHITECTURE.md   # Additional architecture docs
├── requirements.txt         # Python dependencies
└── hansard_scraped.json     # Sample output
```

### Running Tests

```bash
# Run the scraper
python hansard_refactored.py

# Verify output
cat hansard_scraped.json | jq '.tree_branches | length'
```

### Code Quality

The refactored code follows:
- **PEP 8**: Python style guide
- **Type Hints**: Full typing support
- **Docstrings**: Comprehensive documentation
- **Logging**: Structured logging with levels
- **Error Handling**: Try-except blocks with proper logging

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Follow existing code style
4. Add tests if applicable
5. Submit a pull request

## 📝 License

MIT License - Feel free to use and modify as needed.

## 🙏 Acknowledgments

- NSW Parliament for providing the public API
- BeautifulSoup and Requests libraries
- Python community for excellent tools

## 📧 Contact

For issues or questions, please open an issue on the repository.

---

**Note**: This scraper respects the NSW Parliament's API rate limits. For production use, consider implementing rate limiting and caching mechanisms.
