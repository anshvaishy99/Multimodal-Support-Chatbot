import unittest

from app.main import _validate_media, _validate_signature
from app.rag import build_grounded_prompt, retrieve_relevant, split_text
from fastapi import HTTPException


class RagTests(unittest.TestCase):
    def test_split_text_preserves_content_across_chunks(self):
        text = "support " * 400
        chunks = split_text(text, max_chars=100, overlap=10)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))
        self.assertIn("support", " ".join(chunks))

    def test_retrieval_returns_matching_passages_and_prompt_marks_them_untrusted(self):
        candidates = [
            {
                "filename": "guide.txt",
                "page_number": None,
                "chunk_text": "Breathing slowly may help with stress.",
            },
            {
                "filename": "other.txt",
                "page_number": 2,
                "chunk_text": "The recipe uses flour and water.",
            },
        ]
        matches = retrieve_relevant("How can I manage stress?", candidates)
        self.assertEqual(matches[0]["filename"], "guide.txt")
        prompt = build_grounded_prompt("How can I manage stress?", matches)
        self.assertIn("untrusted reference data", prompt)
        self.assertIn("guide.txt", prompt)

    def test_no_match_does_not_claim_document_support(self):
        prompt = build_grounded_prompt("hello", [])
        self.assertIn("No uploaded document passages were relevant", prompt)


class UploadValidationTests(unittest.TestCase):
    def test_extension_and_content_type_must_match(self):
        self.assertEqual(
            _validate_media("photo.png", "image/png", {".png": "image/png"}),
            "image/png",
        )
        with self.assertRaises(HTTPException):
            _validate_media("photo.exe", "image/png", {".png": "image/png"})
        with self.assertRaises(HTTPException):
            _validate_media("photo.png", "text/plain", {".png": "image/png"})

    def test_signature_must_match_declared_image_type(self):
        _validate_signature(b"\x89PNG\r\n\x1a\ncontent", "image/png")
        with self.assertRaises(HTTPException):
            _validate_signature(b"not an image", "image/png")


if __name__ == "__main__":
    unittest.main()
