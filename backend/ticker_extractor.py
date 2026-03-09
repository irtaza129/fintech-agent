"""
Ticker Extraction Layer
-----------------------
Robust multi-strategy ticker detection from financial text:
  1. $AAPL-style cashtag regex
  2. Bare uppercase ticker regex with validation
  3. Company-name-to-ticker mapping (500+ companies)
  4. Common abbreviation / alias handling
  5. False-positive filtering (common English words that look like tickers)
"""

import re
from typing import Dict, List, Set, Optional, Tuple

# ──────────────────────────────────────────────────────────
# 1. COMPANY NAME → TICKER MAP  (S&P 500 + major names)
# ──────────────────────────────────────────────────────────
# Keys are LOWERCASE for case-insensitive lookup.
# Includes full names, common short names, and known aliases.

COMPANY_TO_TICKER: Dict[str, str] = {
    # ── Mega-cap Tech ──
    "apple": "AAPL",
    "apple inc": "AAPL",
    "microsoft": "MSFT",
    "microsoft corp": "MSFT",
    "microsoft corporation": "MSFT",
    "alphabet": "GOOGL",
    "alphabet inc": "GOOGL",
    "google": "GOOGL",
    "amazon": "AMZN",
    "amazon.com": "AMZN",
    "amazon inc": "AMZN",
    "meta": "META",
    "meta platforms": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "nvidia corp": "NVDA",
    "nvidia corporation": "NVDA",
    "tesla": "TSLA",
    "tesla inc": "TSLA",
    "tesla motors": "TSLA",
    "netflix": "NFLX",
    "netflix inc": "NFLX",

    # ── Semiconductors ──
    "advanced micro devices": "AMD",
    "amd": "AMD",
    "intel": "INTC",
    "intel corp": "INTC",
    "intel corporation": "INTC",
    "broadcom": "AVGO",
    "broadcom inc": "AVGO",
    "qualcomm": "QCOM",
    "qualcomm inc": "QCOM",
    "texas instruments": "TXN",
    "micron": "MU",
    "micron technology": "MU",
    "tsmc": "TSM",
    "taiwan semiconductor": "TSM",
    "asml": "ASML",
    "asml holding": "ASML",
    "marvell": "MRVL",
    "marvell technology": "MRVL",
    "arm holdings": "ARM",
    "lam research": "LRCX",
    "applied materials": "AMAT",
    "kla corp": "KLAC",
    "kla corporation": "KLAC",
    "on semiconductor": "ON",
    "onsemi": "ON",
    "synopsys": "SNPS",
    "cadence design": "CDNS",
    "cadence design systems": "CDNS",

    # ── Software / Cloud ──
    "salesforce": "CRM",
    "salesforce inc": "CRM",
    "adobe": "ADBE",
    "adobe inc": "ADBE",
    "oracle": "ORCL",
    "oracle corp": "ORCL",
    "servicenow": "NOW",
    "intuit": "INTU",
    "snowflake": "SNOW",
    "datadog": "DDOG",
    "crowdstrike": "CRWD",
    "crowdstrike holdings": "CRWD",
    "palo alto networks": "PANW",
    "fortinet": "FTNT",
    "zscaler": "ZS",
    "cloudflare": "NET",
    "twilio": "TWLO",
    "mongodb": "MDB",
    "palantir": "PLTR",
    "palantir technologies": "PLTR",
    "shopify": "SHOP",
    "spotify": "SPOT",
    "uber": "UBER",
    "uber technologies": "UBER",
    "lyft": "LYFT",
    "airbnb": "ABNB",
    "doordash": "DASH",
    "snap": "SNAP",
    "snap inc": "SNAP",
    "snapchat": "SNAP",
    "pinterest": "PINS",
    "roblox": "RBLX",
    "unity software": "U",
    "block inc": "SQ",
    "square": "SQ",
    "paypal": "PYPL",
    "paypal holdings": "PYPL",
    "coinbase": "COIN",
    "coinbase global": "COIN",
    "robinhood": "HOOD",
    "robinhood markets": "HOOD",
    "sofi": "SOFI",
    "sofi technologies": "SOFI",
    "affirm": "AFRM",
    "affirm holdings": "AFRM",
    "zoom": "ZM",
    "zoom video": "ZM",
    "zoom video communications": "ZM",
    "docusign": "DOCU",
    "atlassian": "TEAM",
    "hubspot": "HUBS",
    "workday": "WDAY",
    "splunk": "SPLK",
    "elastic": "ESTC",
    "confluent": "CFLT",
    "hashicorp": "HCP",
    "gitlab": "GTLB",

    # ── Big Tech / Internet ──
    "ibm": "IBM",
    "international business machines": "IBM",
    "cisco": "CSCO",
    "cisco systems": "CSCO",
    "hewlett packard": "HPE",
    "hp inc": "HPQ",
    "dell": "DELL",
    "dell technologies": "DELL",

    # ── Finance / Banks ──
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "jpmorgan chase": "JPM",
    "j.p. morgan": "JPM",
    "bank of america": "BAC",
    "bofa": "BAC",
    "wells fargo": "WFC",
    "citigroup": "C",
    "citi": "C",
    "citibank": "C",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "charles schwab": "SCHW",
    "blackrock": "BLK",
    "blackstone": "BX",
    "kkr": "KKR",
    "apollo global": "APO",
    "american express": "AXP",
    "amex": "AXP",
    "visa": "V",
    "mastercard": "MA",
    "capital one": "COF",
    "us bancorp": "USB",
    "pnc financial": "PNC",
    "truist": "TFC",
    "state street": "STT",
    "northern trust": "NTRS",
    "interactive brokers": "IBKR",
    "berkshire hathaway": "BRK.B",
    "berkshire": "BRK.B",

    # ── Insurance ──
    "progressive": "PGR",
    "progressive corp": "PGR",
    "allstate": "ALL",
    "metlife": "MET",
    "prudential": "PRU",
    "aig": "AIG",
    "chubb": "CB",
    "travelers": "TRV",
    "marsh mclennan": "MMC",
    "aon": "AON",

    # ── Healthcare / Pharma ──
    "unitedhealth": "UNH",
    "unitedhealth group": "UNH",
    "johnson & johnson": "JNJ",
    "johnson and johnson": "JNJ",
    "j&j": "JNJ",
    "pfizer": "PFE",
    "eli lilly": "LLY",
    "lilly": "LLY",
    "abbvie": "ABBV",
    "merck": "MRK",
    "merck & co": "MRK",
    "amgen": "AMGN",
    "gilead": "GILD",
    "gilead sciences": "GILD",
    "moderna": "MRNA",
    "regeneron": "REGN",
    "biogen": "BIIB",
    "vertex pharmaceuticals": "VRTX",
    "vertex": "VRTX",
    "bristol myers squibb": "BMY",
    "bristol-myers squibb": "BMY",
    "bms": "BMY",
    "danaher": "DHR",
    "thermo fisher": "TMO",
    "thermo fisher scientific": "TMO",
    "abbott": "ABT",
    "abbott laboratories": "ABT",
    "medtronic": "MDT",
    "stryker": "SYK",
    "intuitive surgical": "ISRG",
    "edwards lifesciences": "EW",
    "boston scientific": "BSX",
    "cigna": "CI",
    "humana": "HUM",
    "cvs health": "CVS",
    "cvs": "CVS",
    "walgreens": "WBA",
    "walgreens boots alliance": "WBA",

    # ── Consumer / Retail ──
    "walmart": "WMT",
    "costco": "COST",
    "target": "TGT",
    "home depot": "HD",
    "the home depot": "HD",
    "lowes": "LOW",
    "lowe's": "LOW",
    "dollar general": "DG",
    "dollar tree": "DLTR",
    "tjx": "TJX",
    "ross stores": "ROST",
    "nike": "NKE",
    "lululemon": "LULU",
    "starbucks": "SBUX",
    "mcdonald's": "MCD",
    "mcdonalds": "MCD",
    "chipotle": "CMG",
    "yum brands": "YUM",
    "coca-cola": "KO",
    "coca cola": "KO",
    "coke": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "procter & gamble": "PG",
    "procter and gamble": "PG",
    "p&g": "PG",
    "colgate": "CL",
    "colgate-palmolive": "CL",
    "unilever": "UL",
    "mondelez": "MDLZ",
    "kraft heinz": "KHC",
    "general mills": "GIS",
    "kellogg": "K",
    "hershey": "HSY",
    "estee lauder": "EL",
    "bath & body works": "BBWI",

    # ── Automotive / EV ──
    "ford": "F",
    "ford motor": "F",
    "general motors": "GM",
    "rivian": "RIVN",
    "lucid": "LCID",
    "lucid motors": "LCID",
    "lucid group": "LCID",
    "nio": "NIO",
    "xpeng": "XPEV",
    "li auto": "LI",
    "toyota": "TM",
    "ferrari": "RACE",

    # ── Energy ──
    "exxon": "XOM",
    "exxon mobil": "XOM",
    "exxonmobil": "XOM",
    "chevron": "CVX",
    "conocophillips": "COP",
    "conoco phillips": "COP",
    "schlumberger": "SLB",
    "halliburton": "HAL",
    "marathon petroleum": "MPC",
    "valero": "VLO",
    "pioneer natural resources": "PXD",
    "devon energy": "DVN",
    "diamondback energy": "FANG",
    "coterra energy": "CTRA",
    "baker hughes": "BKR",
    "enphase": "ENPH",
    "enphase energy": "ENPH",
    "first solar": "FSLR",
    "sunrun": "RUN",
    "nextera energy": "NEE",
    "duke energy": "DUK",
    "southern company": "SO",
    "dominion energy": "D",

    # ── Industrials ──
    "boeing": "BA",
    "lockheed martin": "LMT",
    "raytheon": "RTX",
    "northrop grumman": "NOC",
    "general electric": "GE",
    "honeywell": "HON",
    "3m": "MMM",
    "caterpillar": "CAT",
    "deere": "DE",
    "john deere": "DE",
    "union pacific": "UNP",
    "ups": "UPS",
    "united parcel service": "UPS",
    "fedex": "FDX",
    "waste management": "WM",
    "illinois tool works": "ITW",
    "emerson electric": "EMR",
    "parker hannifin": "PH",

    # ── Telecom / Media ──
    "at&t": "T",
    "att": "T",
    "verizon": "VZ",
    "t-mobile": "TMUS",
    "comcast": "CMCSA",
    "disney": "DIS",
    "walt disney": "DIS",
    "the walt disney company": "DIS",
    "warner bros discovery": "WBD",
    "warner bros": "WBD",
    "paramount": "PARA",
    "paramount global": "PARA",
    "fox corporation": "FOX",
    "fox corp": "FOX",
    "news corp": "NWSA",

    # ── Real Estate / REITs ──
    "prologis": "PLD",
    "american tower": "AMT",
    "crown castle": "CCI",
    "equinix": "EQIX",
    "digital realty": "DLR",
    "simon property": "SPG",
    "simon property group": "SPG",
    "realty income": "O",

    # ── Materials ──
    "freeport-mcmoran": "FCX",
    "freeport mcmoran": "FCX",
    "newmont": "NEM",
    "air products": "APD",
    "linde": "LIN",
    "sherwin-williams": "SHW",
    "sherwin williams": "SHW",
    "dow inc": "DOW",
    "dupont": "DD",

    # ── Crypto-adjacent ──
    "microstrategy": "MSTR",
    "marathon digital": "MARA",
    "riot platforms": "RIOT",
    "riot blockchain": "RIOT",
    "cleanspark": "CLSK",
    "bitfarms": "BITF",

    # ── Chinese Tech ──
    "alibaba": "BABA",
    "tencent": "TCEHY",
    "baidu": "BIDU",
    "jd.com": "JD",
    "pinduoduo": "PDD",
    "pdd holdings": "PDD",

    # ── AI / Trending (2024-2026) ──
    "super micro computer": "SMCI",
    "supermicro": "SMCI",
    "c3.ai": "AI",
    "c3 ai": "AI",
    "soundhound": "SOUN",
    "soundhound ai": "SOUN",
    "bigbear.ai": "BBAI",
    "upstart": "UPST",
    "symbotic": "SYM",
    "serve robotics": "SERV",
    "archer aviation": "ACHR",
    "joby aviation": "JOBY",
    "ionq": "IONQ",
    "quantum computing": "QUBT",
    "rigetti computing": "RGTI",
    "recursion pharmaceuticals": "RXRX",
}

# ──────────────────────────────────────────────────────────
# 2. KNOWN VALID TICKERS  (for bare-ticker validation)
# ──────────────────────────────────────────────────────────

# All unique tickers from the company map
_ALL_MAPPED_TICKERS: Set[str] = set(COMPANY_TO_TICKER.values())

# Additional popular tickers not in the company map
EXTRA_VALID_TICKERS: Set[str] = {
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK", "ARKG",
    "TQQQ", "SQQQ", "UVXY", "VIX",
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "GLD", "SLV", "USO", "UNG",
}

ALL_VALID_TICKERS: Set[str] = _ALL_MAPPED_TICKERS | EXTRA_VALID_TICKERS

# ──────────────────────────────────────────────────────────
# 3. FALSE-POSITIVE BLOCKLIST
# ──────────────────────────────────────────────────────────
# Common English words / abbreviations that look like tickers.

FALSE_POSITIVE_TICKERS: Set[str] = {
    # Common words
    "A", "I", "IT", "IS", "AT", "AN", "AS", "AM", "BE", "BY",
    "DO", "GO", "HE", "IF", "IN", "ME", "MY", "NO", "OF",
    "OK", "ON", "OR", "SO", "TO", "UP", "US", "WE",
    # Common abbreviations
    "AI", "CEO", "CFO", "COO", "CTO", "IPO", "ETF", "GDP",
    "FBI", "SEC", "FED", "USA", "IMF", "NYSE", "DOJ",
    "UK", "EU", "UN", "WHO", "CDC", "FDA",
    "CPI", "PCE", "PMI", "NFP",
    "EV", "AR", "VR", "PR", "HR", "TV", "PC",
    "Q1", "Q2", "Q3", "Q4", "FY", "YOY", "QOQ", "MOM",
    "LLC", "INC", "CO", "LTD", "PLC", "AG", "SA",
    "THE", "FOR", "ALL", "HAS", "HAD", "ARE", "WAS",
    "CAN", "MAY", "NEW", "NOW", "OLD", "OUR", "OUT",
    "OWN", "SAY", "RUN", "SET", "BIG", "TOP", "LOW",
    "HIGH", "BEST", "NEXT", "FAST", "LONG", "REAL",
    "CASH", "FUND", "BOND", "GAIN", "LOSS", "DEAL", "RISK",
    "BULL", "BEAR", "SELL", "HOLD", "RATE", "DEBT",
    "OPEN", "MOVE", "PLAN", "CALL", "POST", "NEWS",
    "TECH", "BANK", "RULE", "FIRM",
    "FREE", "FULL", "HALF", "MOST", "MUCH", "NEAR",
    "WELL", "ALSO", "BACK", "BEEN", "COME", "DOWN",
    "EVEN", "FIND", "GIVE", "GOOD", "HAVE", "HERE",
    "HOME", "JUST", "KEEP", "KNOW", "LAST", "LIKE",
    "LINE", "LIST", "LOOK", "MADE", "MAKE", "MORE",
    "MUST", "ONLY", "OVER", "PART", "PAST", "PICK",
    "PULL", "PUSH", "READ", "RISE", "SAID", "SAME",
    "SHOW", "SIDE", "SIGN", "SOME", "STEP", "SURE",
    "TAKE", "TELL", "THAN", "THAT", "THEM", "THEN",
    "THEY", "THIS", "TIME", "TURN", "VERY", "WANT",
    "WEEK", "WENT", "WERE", "WHAT", "WHEN", "WILL",
    "WITH", "WORK", "YEAR",
}

# Short tickers (1-2 chars) that need extra context to count.
SHORT_TICKERS: Set[str] = {t for t in ALL_VALID_TICKERS if len(t) <= 2}

# Financial context words — if these appear near a bare short ticker,
# we gain confidence it's actually a stock reference.
FINANCIAL_CONTEXT_WORDS = re.compile(
    r'\b(?:stock|shares?|ticker|NYSE|NASDAQ|trading|investor|'
    r'earnings|revenue|dividend|market\s*cap|IPO|SEC|filing|'
    r'bullish|bearish|buy|sell|hold|upgrade|downgrade|'
    r'price\s*target|analyst|quarter|fiscal|eps|revenue|'
    r'portfolio|equit(?:y|ies))\b',
    re.IGNORECASE
)

# ──────────────────────────────────────────────────────────
# 4. REGEX PATTERNS
# ──────────────────────────────────────────────────────────

# Pattern 1: Cashtag  —  $AAPL, $TSLA, $BRK.B
CASHTAG_RE = re.compile(
    r'\$([A-Z]{1,5}(?:\.[A-Z])?)\b'
)

# Pattern 2: Bare uppercase ticker (2-5 chars)
# Must be surrounded by word boundaries, not inside a URL
BARE_TICKER_RE = re.compile(
    r'(?<!\w)(?<!/)(?<!\.)(?<!:)\b([A-Z]{2,5})\b(?!\.\w)'
)

# Pattern 3: Ticker in parentheses  —  "Apple (AAPL)" or "(NASDAQ: TSLA)"
PAREN_TICKER_RE = re.compile(
    r'\(\s*(?:NASDAQ|NYSE|AMEX|OTC)?\s*:?\s*([A-Z]{1,5}(?:\.[A-Z])?)\s*\)'
)


# ──────────────────────────────────────────────────────────
# 5. MAIN EXTRACTION CLASS
# ──────────────────────────────────────────────────────────

class TickerExtractor:
    """
    Multi-strategy ticker extractor for financial text.

    Usage:
        extractor = TickerExtractor()
        tickers = extractor.extract("Apple beat earnings, $TSLA tanked. Nvidia (NVDA) soared.")
        # -> ['AAPL', 'TSLA', 'NVDA']

    You can also pass the user's portfolio tickers for priority matching:
        tickers = extractor.extract(text, portfolio_tickers={'AAPL', 'MSFT'})
    """

    def __init__(self, extra_companies: Optional[Dict[str, str]] = None):
        """
        Args:
            extra_companies: Additional company->ticker mappings to merge in.
                             e.g. {"my startup": "MYCO"}
        """
        self.company_map = dict(COMPANY_TO_TICKER)
        if extra_companies:
            for name, ticker in extra_companies.items():
                self.company_map[name.lower()] = ticker.upper()

        # Pre-compile company name patterns, sorted longest-first
        # so "johnson & johnson" matches before "johnson"
        self._company_patterns: List[Tuple[re.Pattern, str]] = []
        names_sorted = sorted(self.company_map.keys(), key=len, reverse=True)
        for name in names_sorted:
            pattern = re.compile(
                r'\b' + re.escape(name) + r'\b',
                re.IGNORECASE
            )
            self._company_patterns.append((pattern, self.company_map[name]))

    # ──────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────

    def extract(
        self,
        text: str,
        portfolio_tickers: Optional[Set[str]] = None,
        max_tickers: int = 10,
    ) -> List[str]:
        """
        Extract stock tickers from text using all strategies.

        Args:
            text:               The article title + content to scan.
            portfolio_tickers:  User's tracked tickers (always kept if detected).
            max_tickers:        Cap on returned tickers to avoid noise.

        Returns:
            Deduplicated list of ticker symbols, ordered by confidence.
        """
        if not text or not text.strip():
            return []

        results: Dict[str, float] = {}   # ticker -> confidence score

        # Strategy 1: Cashtags ($AAPL)  — highest confidence
        for match in CASHTAG_RE.finditer(text):
            ticker = match.group(1).upper()
            if ticker not in FALSE_POSITIVE_TICKERS or ticker in ALL_VALID_TICKERS:
                results[ticker] = results.get(ticker, 0) + 10.0

        # Strategy 2: Parenthesized tickers — Apple (AAPL), (NASDAQ: TSLA)
        for match in PAREN_TICKER_RE.finditer(text):
            ticker = match.group(1).upper()
            if ticker not in FALSE_POSITIVE_TICKERS:
                results[ticker] = results.get(ticker, 0) + 9.0

        # Strategy 3: Company name matching
        for pattern, ticker in self._company_patterns:
            if pattern.search(text):
                results[ticker] = results.get(ticker, 0) + 8.0

        # Strategy 4: Bare uppercase tickers (lower confidence, needs validation)
        for match in BARE_TICKER_RE.finditer(text):
            candidate = match.group(1).upper()

            # Skip false positives
            if candidate in FALSE_POSITIVE_TICKERS:
                continue

            # Skip short tickers unless they're known valid + have financial context
            if len(candidate) <= 2:
                if candidate in SHORT_TICKERS:
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    window = text[start:end]
                    if FINANCIAL_CONTEXT_WORDS.search(window):
                        results[candidate] = results.get(candidate, 0) + 4.0
                continue

            # For 3-5 char tickers, validate against known list
            if candidate in ALL_VALID_TICKERS:
                results[candidate] = results.get(candidate, 0) + 6.0
            elif portfolio_tickers and candidate in portfolio_tickers:
                # User tracks this ticker, trust it
                results[candidate] = results.get(candidate, 0) + 7.0

        # Boost portfolio tickers (user cares about these)
        if portfolio_tickers:
            for ticker in portfolio_tickers:
                if ticker in results:
                    results[ticker] += 3.0

        # Sort by confidence (descending) and cap
        sorted_tickers = sorted(results.keys(), key=lambda t: results[t], reverse=True)
        return sorted_tickers[:max_tickers]

    def extract_with_details(
        self,
        text: str,
        portfolio_tickers: Optional[Set[str]] = None,
    ) -> List[Dict]:
        """
        Like extract() but returns detailed match info for debugging.

        Returns:
            List of dicts with ticker, confidence score, and detection methods.
        """
        if not text or not text.strip():
            return []

        results: Dict[str, Dict] = {}

        def _add(ticker: str, score: float, method: str):
            if ticker not in results:
                results[ticker] = {"ticker": ticker, "confidence": 0.0, "methods": []}
            results[ticker]["confidence"] += score
            if method not in results[ticker]["methods"]:
                results[ticker]["methods"].append(method)

        # Strategy 1: Cashtags
        for match in CASHTAG_RE.finditer(text):
            ticker = match.group(1).upper()
            if ticker not in FALSE_POSITIVE_TICKERS or ticker in ALL_VALID_TICKERS:
                _add(ticker, 10.0, "cashtag")

        # Strategy 2: Parenthesized
        for match in PAREN_TICKER_RE.finditer(text):
            ticker = match.group(1).upper()
            if ticker not in FALSE_POSITIVE_TICKERS:
                _add(ticker, 9.0, "paren_ticker")

        # Strategy 3: Company names
        for pattern, ticker in self._company_patterns:
            if pattern.search(text):
                _add(ticker, 8.0, "company_name")

        # Strategy 4: Bare tickers
        for match in BARE_TICKER_RE.finditer(text):
            candidate = match.group(1).upper()
            if candidate in FALSE_POSITIVE_TICKERS:
                continue
            if len(candidate) <= 2:
                if candidate in SHORT_TICKERS:
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    window = text[start:end]
                    if FINANCIAL_CONTEXT_WORDS.search(window):
                        _add(candidate, 4.0, "short_ticker_with_context")
                continue
            if candidate in ALL_VALID_TICKERS:
                _add(candidate, 6.0, "bare_ticker")
            elif portfolio_tickers and candidate in portfolio_tickers:
                _add(candidate, 7.0, "portfolio_match")

        # Portfolio boost
        if portfolio_tickers:
            for ticker in portfolio_tickers:
                if ticker in results:
                    results[ticker]["confidence"] += 3.0

        return sorted(results.values(), key=lambda r: r["confidence"], reverse=True)


# ──────────────────────────────────────────────────────────
# 6. MODULE-LEVEL CONVENIENCE
# ──────────────────────────────────────────────────────────

# Singleton for the whole app
_default_extractor: Optional[TickerExtractor] = None


def get_extractor() -> TickerExtractor:
    """Get or create the module-level TickerExtractor singleton."""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = TickerExtractor()
    return _default_extractor


def extract_tickers(
    text: str,
    portfolio_tickers: Optional[Set[str]] = None,
) -> List[str]:
    """
    Convenience function: extract tickers from text.

    >>> extract_tickers("Apple beat earnings, $TSLA down 5%")
    ['AAPL', 'TSLA']
    """
    return get_extractor().extract(text, portfolio_tickers=portfolio_tickers)


def extract_tickers_detailed(
    text: str,
    portfolio_tickers: Optional[Set[str]] = None,
) -> List[Dict]:
    """
    Convenience function: extract tickers with confidence details.

    >>> extract_tickers_detailed("Nvidia (NVDA) soared on AI demand")
    [{'ticker': 'NVDA', 'confidence': 23.0, 'methods': ['paren_ticker', 'company_name', 'bare_ticker']}]
    """
    return get_extractor().extract_with_details(text, portfolio_tickers=portfolio_tickers)
