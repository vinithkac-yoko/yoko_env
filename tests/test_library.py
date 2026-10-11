"""The pattern library: family tree, search, deriving styles, the locked base area."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from yoko_engine.library import (
    LibraryError,
    PatternMeta,
    ancestors,
    descendants,
    family_tree,
    search,
)
from yoko_engine.session import AddBlock
from yoko_io.library import DirectoryLibrary, LockedError

ROOT = Path(__file__).resolve().parents[1]
BASE_ID = "aldrich-womens-6th-basic"


@pytest.fixture
def library(tmp_path: Path) -> DirectoryLibrary:
    """A scratch copy of the library, so tests can derive styles without touching the repo."""
    shutil.copytree(ROOT / "library", tmp_path / "library")
    return DirectoryLibrary(tmp_path / "library", ROOT / "fixtures")


def test_the_basic_set_is_in_the_library_and_locked(library: DirectoryLibrary) -> None:
    metas = library.metas()
    assert set(metas) == {BASE_ID}
    assert metas[BASE_ID].locked and metas[BASE_ID].parent is None
    session = library.session(BASE_ID)
    assert session.read_only
    assert not session.apply(AddBlock("x")).ok
    with pytest.raises(LockedError):
        library.save(BASE_ID, session.pattern)
    with pytest.raises(LockedError):
        library.update_meta(BASE_ID, name="Renamed")


def test_deriving_copies_the_parent_byte_for_byte_and_links_it(library: DirectoryLibrary) -> None:
    meta = library.derive(
        BASE_ID,
        "a-line-skirt",
        "A-line skirt",
        description="Skirt with flare at the hem",
        garment_type="skirt",
        tags=("skirt", "a-line"),
    )
    assert meta.parent == BASE_ID and meta.area == "styles"
    base_file = library.entry(BASE_ID).pattern_path
    assert library.entry("a-line-skirt").pattern_path.read_bytes() == base_file.read_bytes()
    style = library.session("a-line-skirt")
    assert not style.read_only
    assert style.apply(AddBlock("Hem")).ok
    library.save("a-line-skirt", style.pattern)
    assert library.session("a-line-skirt").pattern.blocks[-1].name == "Hem"
    # the parent is untouched
    assert library.session(BASE_ID).pattern.blocks[-1].name != "Hem"


def test_the_family_tree_and_its_queries(library: DirectoryLibrary) -> None:
    library.derive(BASE_ID, "skirt", "Skirt", garment_type="skirt", tags=("skirt",))
    library.derive(
        "skirt", "pencil-skirt", "Pencil skirt", garment_type="skirt", tags=("skirt", "pencil")
    )
    library.derive(
        "skirt", "a-line-skirt", "A-line skirt", garment_type="skirt", tags=("skirt", "a-line")
    )
    library.derive(BASE_ID, "trousers", "Trousers", garment_type="trousers", tags=("trousers",))
    metas = library.metas()
    tree = family_tree(metas)
    assert [n.meta.id for n in tree] == [BASE_ID]
    assert [c.meta.id for c in tree[0].children] == ["skirt", "trousers"]
    assert [c.meta.id for c in tree[0].children[0].children] == ["a-line-skirt", "pencil-skirt"]
    assert [m.id for m in ancestors(metas, "pencil-skirt")] == ["skirt", BASE_ID]
    assert {m.id for m in descendants(metas, BASE_ID)} == {
        "skirt", "trousers", "pencil-skirt", "a-line-skirt",
    }  # fmt: skip
    assert tree[0].to_dict()["children"][0]["children"][0]["id"] == "a-line-skirt"  # type: ignore[index]


def test_search_by_tags_garment_type_and_text(library: DirectoryLibrary) -> None:
    library.derive(
        BASE_ID, "a-line-skirt", "A-line skirt", description="flared hem", garment_type="skirt",
        tags=("skirt", "a-line"),
    )  # fmt: skip
    library.derive(
        BASE_ID,
        "slim-trousers",
        "Slim trousers",
        garment_type="trousers",
        tags=("trousers", "slim"),
    )
    metas = library.metas().values()
    assert [m.id for m in search(metas, tags=["a-line"])] == ["a-line-skirt"]
    assert [m.id for m in search(metas, garment_type="trousers")] == ["slim-trousers"]
    assert [m.id for m in search(metas, "flared")] == ["a-line-skirt"]
    assert search(metas, "dress") == []
    best = search(metas, "skirt")
    assert best[0].id == "a-line-skirt"  # a name match beats a tag match
    assert [m.id for m in search(metas, area="base")] == [BASE_ID]
    assert len(search(metas, limit=1)) == 1


def test_bad_derivations_are_refused(library: DirectoryLibrary) -> None:
    for args, code in (
        (("nope", "x", "X"), "unknown_pattern"),
        ((BASE_ID, BASE_ID, "X"), "duplicate_id"),
        ((BASE_ID, "Bad Id", "X"), "bad_id"),
        ((BASE_ID, "ok", "  "), "empty_name"),
    ):
        with pytest.raises(LibraryError) as err:
            library.derive(*args)
        assert err.value.code == code


def test_a_broken_family_tree_is_reported() -> None:
    a = PatternMeta("a", "A", parent="b")
    b = PatternMeta("b", "B", parent="a")
    with pytest.raises(LibraryError) as err:
        family_tree({"a": a, "b": b})
    assert err.value.code == "cycle"
    with pytest.raises(LibraryError) as err2:
        family_tree({"a": PatternMeta("a", "A", parent="ghost")})
    assert err2.value.code == "unknown_parent"
    with pytest.raises(LibraryError) as err3:
        family_tree({"a": PatternMeta("a", "A", area="base", parent="a")})
    assert err3.value.code in ("base_has_parent", "cycle")
