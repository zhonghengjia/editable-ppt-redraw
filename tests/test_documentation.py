"""Keep conditional contracts reachable and their local links resolvable."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def prose(path):
    text = path.read_text(encoding='utf-8')
    return re.sub(r'(?ms)^(`{3,}|~{3,}).*?^\1\s*$', '', text)


def anchors(path):
    counts, result = {}, set()
    for heading in re.findall(r'(?m)^#{1,6}\s+(.+?)\s*#*$', prose(path)):
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        n = counts.get(slug, 0)
        result.add(slug + (f'-{n}' if n else ''))
        counts[slug] = n + 1
    return result


def links(path):
    for value in re.findall(r'\[[^\]\n]*\]\(([^\s)]+)\)', prose(path)):
        parsed = urlsplit(value.strip('<>'))
        if parsed.scheme or parsed.netloc:
            continue
        yield (path.parent / unquote(parsed.path)).resolve() if parsed.path else path, unquote(parsed.fragment)


class DocumentationTests(unittest.TestCase):
    def test_local_paths_and_fragments_resolve(self):
        pages = list(ROOT.glob('*.md')) + list((ROOT / 'references').glob('*.md'))
        for page in pages:
            for target, fragment in links(page):
                with self.subTest(page=page.relative_to(ROOT), target=str(target), fragment=fragment):
                    self.assertTrue(target.is_relative_to(ROOT), 'Local documentation link escapes package')
                    self.assertTrue(target.exists(), 'Missing local documentation target')
                    if fragment and target.suffix == '.md':
                        self.assertIn(fragment, anchors(target), 'Missing Markdown heading anchor')

    def test_all_reference_contracts_are_discoverable(self):
        pending, seen = [ROOT / 'SKILL.md'], set()
        while pending:
            path = pending.pop()
            if path in seen:
                continue
            seen.add(path)
            for target, _ in links(path):
                if target.suffix == '.md' and target.is_file() and target.is_relative_to(ROOT):
                    pending.append(target)
        self.assertFalse(set((ROOT / 'references').glob('*.md')) - seen,
                         'A reference has no route from the skill entrypoint')


if __name__ == '__main__':
    unittest.main()
