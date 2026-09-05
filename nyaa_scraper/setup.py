from setuptools import setup, find_packages

setup(
    name="nyaa-scraper",
    version="2.0.0",
    description="Production-grade anime release discovery, parsing and quality ranking",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.27,<1",
        "beautifulsoup4>=4.12,<5",
        "lxml>=5,<7",
        "thefuzz>=0.22,<1",
        "python-Levenshtein>=0.25,<1",
        "feedparser>=6,<7",
        "pydantic>=2,<3",
        "rich>=13,<15",
        "click>=8.1,<9",
        "aniparse>=1,<3",
    ],
    entry_points={"console_scripts": ["nyaa-scraper=nyaa_scraper.cli:cli"]},
    classifiers=["Programming Language :: Python :: 3.11", "Operating System :: OS Independent"],
)
