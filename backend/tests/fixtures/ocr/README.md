# Difficult scanned philosophy fixture

The real-OCR integration test generates an image-only PDF at runtime from a
short public-domain excerpt of George Long's translation of Marcus Aurelius,
*Meditations*, Book II. The image is deliberately rendered as a faint,
slightly skewed grayscale scan with serif type and degraded JPEG quality.

Source provenance: Project Gutenberg, `Meditations` by Marcus Aurelius,
translated by George Long:
https://www.gutenberg.org/ebooks/2680

The PDF is generated in pytest's temporary directory and is never stored as a
replacement for the original ingested bytes.
