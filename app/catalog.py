"""The textbooks the assistant knows about.

NCERT names every chapter PDF with a short code. For example "jesc105.pdf":

    j    class      a = 1, b = 2, c = 3 ... j = 10, k = 11, l = 12
    e    medium     e = English, h = Hindi, u = Urdu
    sc   book       ff = First Flight, sc = Science, ss = Social Science, ...
    1    volume
    05   chapter number

So the first five letters ("jesc1") name the book and the last two digits
are the chapter.

To add a book (for example Class 8 Science, code "hesc1"):
    1. download its chapter PDFs from https://ncert.nic.in/textbook.php
    2. put them anywhere under data/, e.g. data/class-8/science/
    3. add an entry to BOOKS below
    4. run `python -m app.ingest` again
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Book:
    grade: int
    subject: str
    title: str
    chapters: tuple[str, ...]
    file: str | None = None


BOOKS = {
    # Class 5: short demo books written for this project (not NCERT books). Their
    # topics overlap the Class 10 books, to show that each class gets its own answer.
    "eeen1": Book(
        grade=5,
        subject="English",
        title="Sunshine Reader - demo",
        chapters=(
            "The Thirsty Crow",
            "Meena's Kite",
            "A Letter to Grandma",
            "Tara the Otter",
            "Raghu and the Rain",
        ),
    ),
    "eesc1": Book(
        grade=5,
        subject="Science",
        title="Science Around Us - demo",
        chapters=(
            "How Plants Make Their Food",
            "Light and Shadows",
            "Electricity Around Us",
            "Our Senses and Our Eyes",
            "Taking Care of Our Environment",
        ),
    ),
    "eess1": Book(
        grade=5,
        subject="Social Science",
        title="Our Land and People - demo",
        chapters=(
            "Soil: The Ground Beneath Our Feet",
            "Forests and Wild Animals",
            "Water: Our Precious Friend",
            "Farmers and Farming",
            "Travelling and Sending Messages",
        ),
    ),
    # Class 10: NCERT books
    "jeff1": Book(
        grade=10,
        subject="English",
        title="First Flight",
        chapters=(
            "A Letter to God",
            "Nelson Mandela: Long Walk to Freedom",
            "Two Stories about Flying",
            "From the Diary of Anne Frank",
            "Glimpses of India",
            "Mijbil the Otter",
            "Madam Rides the Bus",
            "The Sermon at Benares",
            "The Proposal",
        ),
    ),
    "jesc1": Book(
        grade=10,
        subject="Science",
        title="Science",
        chapters=(
            "Chemical Reactions and Equations",
            "Acids, Bases and Salts",
            "Metals and Non-metals",
            "Carbon and its Compounds",
            "Life Processes",
            "Control and Coordination",
            "How do Organisms Reproduce?",
            "Heredity",
            "Light – Reflection and Refraction",
            "The Human Eye and the Colourful World",
            "Electricity",
            "Magnetic Effects of Electric Current",
            "Our Environment",
        ),
    ),
    "jess1": Book(
        grade=10,
        subject="Social Science",
        title="Contemporary India II (Geography)",
        chapters=(
            "Resources and Development",
            "Forest and Wildlife Resources",
            "Water Resources",
            "Agriculture",
            "Minerals and Energy Resources",
            "Manufacturing Industries",
            "Lifelines of National Economy",
        ),
    ),
}


def chapter_info(pdf_name: str) -> dict | None:
    """Metadata for one chapter PDF, or None if it isn't a chapter of a known book.

    >>> chapter_info("jesc105.pdf")["chapter_title"]
    'Life Processes'
    """
    code = Path(pdf_name).stem.lower()
    book = BOOKS.get(code[:5])
    chapter = code[5:]

    # Skips unknown books and extras like "jesc1ps.pdf" (the contents pages)
    if book is None or not chapter.isdigit():
        return None

    number = int(chapter)
    if 1 <= number <= len(book.chapters):
        title = book.chapters[number - 1]
    else:
        title = f"Chapter {number}"

    return {
        "grade": book.grade,
        "subject": book.subject,
        "book": book.title,
        "chapter": number,
        "chapter_title": title,
    }


# ------------------------------------------------------------- custom books ---

CUSTOM_BOOKS_FILE = settings.storage_dir / "custom_books.json"


def load_custom_books() -> dict[str, Book]:
    """Load parent-uploaded or custom curriculum books from disk."""
    if not CUSTOM_BOOKS_FILE.exists():
        return {}
    try:
        data = json.loads(CUSTOM_BOOKS_FILE.read_text(encoding="utf-8"))
        custom = {}
        for code, b in data.items():
            custom[code] = Book(
                grade=b["grade"],
                subject=b["subject"],
                title=b["title"],
                chapters=tuple(b.get("chapters", ())),
                file=b.get("file"),
            )
        return custom
    except Exception as e:
        log.warning("Failed to load custom books from %s: %s", CUSTOM_BOOKS_FILE, e)
        return {}


def register_custom_book(
    code: str,
    grade: int,
    subject: str,
    title: str,
    chapters: tuple[str, ...] | list[str],
    file: str | None = None,
) -> Book:
    """Register and persist a newly uploaded custom textbook."""
    book = Book(
        grade=grade,
        subject=subject,
        title=title,
        chapters=tuple(chapters),
        file=file,
    )
    BOOKS[code] = book
    try:
        CUSTOM_BOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if CUSTOM_BOOKS_FILE.exists():
            existing = json.loads(CUSTOM_BOOKS_FILE.read_text(encoding="utf-8"))
        existing[code] = {
            "grade": grade,
            "subject": subject,
            "title": title,
            "chapters": list(chapters),
            "file": file,
        }
        CUSTOM_BOOKS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("Failed to save custom book to %s: %s", CUSTOM_BOOKS_FILE, e)
    return book


def remove_custom_book(code: str) -> bool:
    """Unregister and remove an uploaded custom textbook from the active catalog."""
    if code in BOOKS:
        del BOOKS[code]
    try:
        if CUSTOM_BOOKS_FILE.exists():
            existing = json.loads(CUSTOM_BOOKS_FILE.read_text(encoding="utf-8"))
            if code in existing:
                del existing[code]
                CUSTOM_BOOKS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
                return True
    except Exception as e:
        log.warning("Failed to remove custom book from %s: %s", CUSTOM_BOOKS_FILE, e)
    return False


# Register any custom books saved previously
BOOKS.update(load_custom_books())

