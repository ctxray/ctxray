"""TF-IDF analysis and K-means clustering."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

# Regex for mixed Chinese/English tokenization (no extra deps)
_ZH_BLOCK = re.compile(r"[一-鿿㐀-䶿豈-﫿]+")
_ASCII_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9]*(?:[_.\-][a-zA-Z0-9]+)*")

# Generic terms that saturate coding prompt corpora and carry no analytical signal.
# Derived from: arXiv:2303.10439 (SE stop words), prompt engineering guides,
# and analysis of AI coding assistant interaction patterns.
_CODING_STOP_WORDS: frozenset[str] = frozenset(
    {
        # --- Generic instruction verbs (appear in nearly every coding prompt) ---
        "write",
        "create",
        "implement",
        "build",
        "make",
        "generate",
        "produce",
        "develop",
        "add",
        "update",
        "modify",
        "change",
        "fix",
        "refactor",
        "rewrite",
        "convert",
        "check",
        "verify",
        "test",
        "debug",
        "review",
        "analyze",
        "optimize",
        "improve",
        "remove",
        "delete",
        "replace",
        "rename",
        "setup",
        "configure",
        # --- Generic programming structure nouns ---
        "function",
        "method",
        "class",
        "object",
        "module",
        "package",
        "library",
        "variable",
        "constant",
        "parameter",
        "argument",
        "attribute",
        "property",
        "field",
        "type",
        "interface",
        "struct",
        "trait",
        "protocol",
        # --- Generic data type nouns ---
        "string",
        "integer",
        "float",
        "boolean",
        "number",
        "char",
        "byte",
        "null",
        "nil",
        "none",
        "undefined",
        "void",
        # --- Generic collection nouns ---
        "array",
        "list",
        "dict",
        "dictionary",
        "map",
        "set",
        "tuple",
        "vector",
        # --- Generic code/project structure ---
        "code",
        "file",
        "directory",
        "folder",
        "path",
        "project",
        "repo",
        "codebase",
        "script",
        "program",
        "source",
        "line",
        "block",
        "scope",
        # --- Generic I/O and execution verbs ---
        "run",
        "execute",
        "call",
        "invoke",
        "return",
        "output",
        "print",
        "display",
        "render",
        "parse",
        "process",
        "handle",
        "validate",
        "transform",
        "load",
        "save",
        "store",
        "fetch",
        "retrieve",
        "send",
        "receive",
        "read",
        "import",
        "export",
        # --- LeetCode / algorithm template words ---
        "given",
        "input",
        "output",
        "expected",
        "constraints",
        "assume",
        "ascending",
        "descending",
        "sorted",
        "optimal",
        "brute",
        # --- AI assistant interaction boilerplate ---
        "please",
        "thanks",
        "help",
        "explain",
        "provide",
        "ensure",
        "following",
        "example",
        "basically",
        "simply",
        "just",
        "actually",
        # --- High-frequency SE terms (arXiv:2303.10439) ---
        "use",
        "using",
        "used",
        "want",
        "work",
        "working",
        "need",
        "try",
        "like",
        "get",
        "know",
        "new",
        "possible",
        "specific",
        "simple",
        "right",
        "correct",
        "good",
        "better",
        "best",
        "sure",
        # --- AI tool names (high-frequency for their own users, no analytical signal) ---
        "claude",
        "cursor",
        "aider",
        "gemini",
        # --- Shell tools and package managers ---
        "cd",
        "uv",
        "pip",
        "npm",
        "yarn",
        "pnpm",
        "brew",
        "apt",
        "git",
        "bash",
        "sh",
        "zsh",
        "python",
        "python3",
        "node",
        "pytest",
        "make",
        "docker",
        "kubectl",
        "curl",
        "wget",
        "ssh",
        "sudo",
    }
)

# Chinese conversational/instruction stop words (HIT + cn_stopwords, curated for short text)
_CHINESE_STOP_WORDS: frozenset[str] = frozenset(
    {
        # Particles (助词/语气词)
        "的",
        "了",
        "吗",
        "呢",
        "吧",
        "啊",
        "哦",
        "嗯",
        "哈",
        "呀",
        "嘛",
        "哎",
        "唉",
        "哟",
        # Pronouns (代词)
        "我",
        "你",
        "他",
        "她",
        "它",
        "我们",
        "你们",
        "他们",
        "她们",
        "大家",
        # Demonstratives (指示代词)
        "这",
        "那",
        "这个",
        "那个",
        "这些",
        "那些",
        "这里",
        "那里",
        "这样",
        "那样",
        # Question words (疑问词)
        "什么",
        "哪",
        "谁",
        "哪个",
        "哪里",
        "怎么",
        "为什么",
        "怎样",
        "如何",
        "什么样",
        # Conjunctions (连词)
        "和",
        "与",
        "或",
        "但",
        "但是",
        "而且",
        "因为",
        "所以",
        "虽然",
        "然而",
        "如果",
        "还是",
        "不过",
        "而",
        "及",
        "还有",
        "并且",
        "或者",
        "不然",
        # Adverbs (副词)
        "也",
        "都",
        "还",
        "又",
        "再",
        "很",
        "非常",
        "太",
        "真的",
        "确实",
        "其实",
        "只是",
        "就是",
        "已经",
        "一直",
        "比较",
        "特别",
        # Modals/auxiliaries (助动词)
        "要",
        "会",
        "能",
        "可以",
        "需要",
        "应该",
        "必须",
        "可能",
        "想",
        "愿意",
        # High-frequency instruction verbs (常见动词)
        "是",
        "有",
        "知道",
        "觉得",
        "看",
        "说",
        "做",
        "用",
        "看看",
        "试试",
        # Prepositions (介词)
        "在",
        "从",
        "到",
        "对",
        "为",
        "于",
        "向",
        "以",
        "按",
        "给",
        "把",
        "被",
        # Time & sequence words (时间/顺序词)
        "现在",
        "刚才",
        "之前",
        "之后",
        "最近",
        "目前",
        "当前",
        "首先",
        "然后",
        "接下来",
        "最后",
        "其次",
        "总之",
        # Discourse markers (话语标记)
        "好的",
        "好",
        "明白",
        "了解",
        "行",
        "好吧",
        "没问题",
        # Common connectives & auxiliary bigrams
        "是否",
        "们的",
        "否则",
        "这是",
        "那是",
        "就是",
        "只是",
        "但是",
        "所以",
        "因为",
        "如果",
        "虽然",
        "然而",
        "不过",
        # Negation (否定词)
        "不",
        "没",
        "别",
        "无",
        "不是",
        "没有",
        "不要",
        # Quantity (数量)
        "一",
        "一些",
        "一个",
        "几个",
        "很多",
        "所有",
        "每个",
        "各种",
        "一下",
        # Generic domain nouns (too broad to be analytical signals)
        "项目",
        "代码",
        "文件",
        "功能",
        "问题",
        "错误",
        "测试",
        "版本",
    }
)

# Conversational English stop words missing from sklearn's built-in list
# (sklearn uses Stone 2010 which targets formal text, not chat/instructions)
_CONVERSATIONAL_EN_STOP_WORDS: frozenset[str] = frozenset(
    {
        # Acknowledgments
        "yes",
        "yeah",
        "yep",
        "yup",
        "okay",
        "ok",
        "alright",
        "gotcha",
        "noted",
        "understood",
        # Politeness
        "hello",
        "hey",
        "hi",
        "sorry",
        "oops",
        "hmm",
        # Contraction artifacts (sklearn tokenizes "doesn't" → "doesn" + "t")
        "doesn",
        "wouldn",
        "couldn",
        "shouldn",
        "hadn",
        "hasn",
        "isn",
        "aren",
        "wasn",
        "weren",
        # Common verbs sklearn misses (its list is based on Stone 2010, formal text)
        "does",
        "did",
        "do",
        "going",
        "gone",
        "got",
        "let",
        "lets",
        # Hedges / intensifiers
        "really",
        "pretty",
        "quite",
        "fairly",
        "rather",
        "somewhat",
        "maybe",
        "perhaps",
        "probably",
        "likely",
        # Discourse connectors
        "also",
        "anyway",
        "though",
        "however",
        "literally",
        "essentially",
    }
)

# Merged stop word set: English + coding domain + conversational + Chinese
STOP_WORDS: frozenset[str] = (
    ENGLISH_STOP_WORDS | _CODING_STOP_WORDS | _CONVERSATIONAL_EN_STOP_WORDS | _CHINESE_STOP_WORDS
)


def _tokenize_mixed(text: str) -> list[str]:
    """Tokenize mixed Chinese/English text without extra dependencies.

    Strategy:
    - Chinese character runs → character bigrams (semantically dense for short text)
    - ASCII words/identifiers → lowercased whole words (length >= 2)
    - Punctuation, numbers, spaces → dropped

    Stop words are NOT applied here; call _mixed_zh_en_analyzer for filtered output.
    """
    tokens: list[str] = []
    pos = 0
    while pos < len(text):
        m = _ZH_BLOCK.match(text, pos)
        if m:
            chars = list(m.group())
            # Bigrams only — single Chinese chars are almost always stop words or
            # partial words (们 only in 我们, 么 only in 什么). Bigrams are semantically
            # rich: 报错, 修复, 中间件, 认证, 配置 etc.
            tokens.extend(chars[i] + chars[i + 1] for i in range(len(chars) - 1))
            pos = m.end()
            continue
        m = _ASCII_WORD.match(text, pos)
        if m:
            word = m.group().lower()
            if len(word) >= 2:
                tokens.append(word)
            pos = m.end()
            continue
        pos += 1
    return tokens


def _mixed_zh_en_analyzer(text: str) -> list[str]:
    """Custom analyzer for TfidfVectorizer handling mixed Chinese/English prompts.

    When analyzer= is a callable, sklearn ignores stop_words=. Stop word filtering
    is applied here directly so the merged STOP_WORDS set (EN + ZH) takes effect.
    """
    return [t for t in _tokenize_mixed(text) if t not in STOP_WORDS]


def _is_noise_phrase(term: str) -> bool:
    """Filter out path fragments, usernames, year numbers, and other noise from TF-IDF results."""
    noise_tokens = {"users", "chris", "projects", "home", "usr", "var", "tmp", "src", "py"}
    words = set(term.lower().split())
    # Skip if majority of words are path/noise tokens
    if len(words & noise_tokens) >= len(words) * 0.5:
        return True
    # Skip phrases that are purely year numbers (e.g. "2025 2026")
    if all(re.fullmatch(r"20\d\d", w) for w in term.split()):
        return True
    # Skip phrases composed entirely of shell/tool stop words
    shell_words = {"cd", "uv", "pip", "pytest", "git", "bash", "python", "python3", "npm"}
    if words <= shell_words:
        return True
    return False


def compute_tfidf_stats(texts: list[str], top_n: int = 20) -> list[dict[str, Any]]:
    """Compute TF-IDF stats on meaningful phrases (unigrams through trigrams).

    Uses unigrams + bigrams + trigrams with English and coding domain stop words removed.
    sublinear_tf dampens high-frequency terms; max_df=0.8 auto-removes corpus-ubiquitous words.

    Returns list of dicts: [{"term": str, "count": int, "df": int, "tfidf_avg": float}]
    """
    if not texts:
        return []

    # Pre-process: strip file paths and year numbers to avoid noise n-grams
    path_re = re.compile(r"[~/][\w./-]{10,}")
    year_re = re.compile(r"\b20\d\d\b")
    cleaned = [year_re.sub("", path_re.sub("", t)) for t in texts]

    # Try n-grams first (meaningful phrases), fall back to unigrams for small datasets
    min_df = 2 if len(cleaned) >= 10 else 1
    try:
        # analyzer= handles mixed ZH/EN tokenization + stop word filtering internally.
        # When analyzer is callable, sklearn ignores ngram_range and stop_words.
        vectorizer = TfidfVectorizer(
            analyzer=_mixed_zh_en_analyzer,
            max_features=5000,
            min_df=min_df,
            sublinear_tf=True,
            max_df=0.8,
        )
        tfidf_matrix = vectorizer.fit_transform(cleaned)
        feature_names = vectorizer.get_feature_names_out()
    except ValueError:
        feature_names = np.array([])

    if len(feature_names) == 0:
        # Fallback to unigrams if not enough data for n-grams
        vectorizer = TfidfVectorizer(
            analyzer=_mixed_zh_en_analyzer,
            max_features=5000,
            sublinear_tf=True,
        )
        tfidf_matrix = vectorizer.fit_transform(cleaned)
        feature_names = vectorizer.get_feature_names_out()

    # Average TF-IDF score per term across all documents
    avg_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()

    # Document frequency (number of docs containing each term)
    df = np.asarray((tfidf_matrix > 0).sum(axis=0)).flatten()

    # Sum of TF-IDF weights (approximate count)
    count = np.asarray(tfidf_matrix.sum(axis=0)).flatten()

    results = []
    for i, term in enumerate(feature_names):
        if _is_noise_phrase(term):
            continue
        results.append(
            {
                "term": term,
                "count": int(count[i] * len(texts)),
                "df": int(df[i]),
                "tfidf_avg": float(avg_scores[i]),
            }
        )

    results.sort(key=lambda x: x["tfidf_avg"], reverse=True)
    return results[:top_n]


def _best_k(X: Any, max_k: int = 15) -> int:
    """Select optimal K for K-means via silhouette score sweep (K=3..max_k).

    Returns the K with the highest average silhouette score.
    Falls back to K=3 if the dataset is too small to evaluate.
    """
    n = X.shape[0] if hasattr(X, "shape") else len(X)
    k_min = 3
    k_max = min(max_k, n - 1)
    if k_min > k_max:
        return max(2, n - 1)

    best_k, best_score = k_min, -1.0
    for k in range(k_min, k_max + 1):
        labels = KMeans(n_clusters=k, random_state=42, n_init=5).fit_predict(X)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(X, labels, sample_size=min(1000, n)))
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def cluster_prompts(texts: list[str], n_clusters: int | None = None) -> dict[int, list[str]]:
    """Cluster prompts using LSA-reduced TF-IDF vectors with K-means.

    When n_clusters is None (default), automatically selects the optimal K using a
    silhouette score sweep over K=3..15. Pass an explicit integer to override.

    Applies TruncatedSVD (LSA) + L2 normalization before K-means to avoid the
    single-dominant-cluster problem caused by sparse high-dimensional TF-IDF vectors
    on short text. See: scikit-learn text clustering example (plot_document_clustering).

    Returns {cluster_id: [texts]}
    """
    if not texts:
        return {}

    vectorizer = TfidfVectorizer(
        analyzer=_mixed_zh_en_analyzer,
        max_features=5000,
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    # LSA: reduce to 50 dims + L2-normalize for cosine-friendly K-means
    n_components = min(50, tfidf_matrix.shape[1] - 1, len(texts) - 1)
    if n_components >= 2:
        lsa = make_pipeline(TruncatedSVD(n_components=n_components, random_state=42), Normalizer())
        X: Any = lsa.fit_transform(tfidf_matrix)
    else:
        X = tfidf_matrix

    k = _best_k(X) if n_clusters is None else min(n_clusters, len(texts))

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    clusters: dict[int, list[str]] = {}
    for text, label in zip(texts, labels):
        clusters.setdefault(int(label), []).append(text)

    return clusters
