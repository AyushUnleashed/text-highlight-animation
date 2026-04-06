"""Grade all eval outputs against assertions."""
import json
import os
import re
import glob

WORKSPACE = os.path.dirname(os.path.abspath(__file__))

EVALS = [
    {
        "name": "exact-lines-blog",
        "variants": ["with_skill", "without_skill"],
        "assertions": [
            {"id": "tsx-file-exists", "text": "A .tsx component file was created in src/text-highlights/"},
            {"id": "root-tsx-updated", "text": "Root.tsx contains a <Composition> entry for the new component"},
            {"id": "correct-line-count", "text": "The generated TSX defines exactly 4 highlight lines"},
            {"id": "uses-remotion-apis", "text": "TSX uses useCurrentFrame, spring, and staticFile from remotion"},
            {"id": "references-correct-image", "text": "TSX references blog-screenshot.png via staticFile()"},
        ],
    },
    {
        "name": "vague-paragraph-tweet",
        "variants": ["with_skill", "without_skill"],
        "assertions": [
            {"id": "tsx-file-exists", "text": "A .tsx component file was created in src/text-highlights/"},
            {"id": "root-tsx-updated", "text": "Root.tsx contains a <Composition> entry for the new component"},
            {"id": "references-correct-image", "text": "TSX references tweet_sample.png via staticFile()"},
            {"id": "reasonable-line-selection", "text": "Highlighted lines form a coherent group (2+ lines)"},
        ],
    },
    {
        "name": "marker-style-blog",
        "variants": ["with_skill", "without_skill"],
        "assertions": [
            {"id": "tsx-file-exists", "text": "A .tsx component file was created in src/text-highlights/"},
            {"id": "root-tsx-updated", "text": "Root.tsx contains a <Composition> entry for the new component"},
            {"id": "marker-mode-used", "text": "TSX uses normal blend mode (marker style), not difference (invert)"},
            {"id": "yellow-color", "text": "TSX uses a yellow-ish highlight color"},
            {"id": "correct-line-count", "text": "The generated TSX defines exactly 4 highlight lines (lines 13-16)"},
        ],
    },
]


def find_tsx(outputs_dir):
    """Find the first .tsx file in outputs (not Root.tsx)."""
    for f in os.listdir(outputs_dir):
        if f.endswith(".tsx") and f != "Root.tsx":
            return os.path.join(outputs_dir, f)
    return None


def read_file(path):
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def grade_run(eval_info, variant, outputs_dir):
    tsx_path = find_tsx(outputs_dir)
    tsx = read_file(tsx_path)
    root = read_file(os.path.join(outputs_dir, "Root.tsx"))

    results = []
    for assertion in eval_info["assertions"]:
        aid = assertion["id"]
        passed = False
        evidence = ""

        if aid == "tsx-file-exists":
            passed = tsx_path is not None and len(tsx) > 0
            evidence = f"Found: {os.path.basename(tsx_path)}" if passed else "No .tsx file found"

        elif aid == "root-tsx-updated":
            # Check for any Composition entry
            passed = "<Composition" in root and "component={" in root
            evidence = "Composition entry found" if passed else "No Composition in Root.tsx"

        elif aid == "correct-line-count":
            # Count highlight line definitions (objects with top/left/width/height)
            line_matches = re.findall(r'\{\s*top:\s*[\d.]+', tsx)
            count = len(line_matches)
            passed = count == 4
            evidence = f"Found {count} highlight lines (expected 4)"

        elif aid == "uses-remotion-apis":
            has_frame = "useCurrentFrame" in tsx
            has_spring = "spring" in tsx or "interpolate" in tsx
            has_static = "staticFile" in tsx
            passed = has_frame and has_spring and has_static
            missing = []
            if not has_frame: missing.append("useCurrentFrame")
            if not has_spring: missing.append("spring/interpolate")
            if not has_static: missing.append("staticFile")
            evidence = "All present" if passed else f"Missing: {', '.join(missing)}"

        elif aid == "references-correct-image":
            if "tweet" in eval_info["name"]:
                passed = "tweet_sample.png" in tsx
                evidence = "References tweet_sample.png" if passed else "Wrong or missing image reference"
            else:
                passed = "blog-screenshot.png" in tsx
                evidence = "References blog-screenshot.png" if passed else "Wrong or missing image reference"

        elif aid == "reasonable-line-selection":
            line_matches = re.findall(r'\{\s*top:\s*[\d.]+', tsx)
            count = len(line_matches)
            passed = count >= 2
            evidence = f"Found {count} highlight lines (need >= 2 for a paragraph)"

        elif aid == "marker-mode-used":
            has_normal = "'normal'" in tsx or '"normal"' in tsx
            has_no_difference = "'difference'" not in tsx and '"difference"' not in tsx
            passed = has_normal or has_no_difference
            if "'difference'" in tsx or '"difference"' in tsx:
                evidence = "Uses difference blend mode (invert style, not marker)"
                passed = False
            elif has_normal:
                evidence = "Uses normal blend mode (marker style)"
            else:
                evidence = "No blend mode specified (could be marker)"

        elif aid == "yellow-color":
            # Check for yellow-ish colors
            yellow_patterns = ["#FFE066", "#ffe066", "#FFFF00", "#ffff00", "#FFC", "#ffd", "yellow", "#FFD", "#FFE", "#ffc"]
            found = any(p.lower() in tsx.lower() for p in yellow_patterns)
            passed = found
            color_match = re.search(r"(?:HIGHLIGHT_COLOR|color|backgroundColor)\s*[:=]\s*['\"]([^'\"]+)['\"]", tsx)
            if color_match:
                evidence = f"Color found: {color_match.group(1)}"
            else:
                evidence = "Yellow color found" if passed else "No yellow color detected"

        results.append({
            "text": assertion["text"],
            "passed": passed,
            "evidence": evidence,
        })

    return results


def main():
    for eval_info in EVALS:
        for variant in eval_info["variants"]:
            outputs_dir = os.path.join(WORKSPACE, eval_info["name"], variant, "outputs")
            if not os.path.exists(outputs_dir):
                print(f"SKIP {eval_info['name']}/{variant} — no outputs dir")
                continue

            results = grade_run(eval_info, variant, outputs_dir)
            grading = {
                "eval_name": eval_info["name"],
                "variant": variant,
                "expectations": results,
            }

            grading_path = os.path.join(WORKSPACE, eval_info["name"], variant, "grading.json")
            with open(grading_path, "w") as f:
                json.dump(grading, f, indent=2)

            passed = sum(1 for r in results if r["passed"])
            total = len(results)
            status = "PASS" if passed == total else "PARTIAL" if passed > 0 else "FAIL"
            print(f"{status} {eval_info['name']}/{variant}: {passed}/{total}")
            for r in results:
                mark = "✓" if r["passed"] else "✗"
                print(f"  {mark} {r['text']}: {r['evidence']}")
            print()


if __name__ == "__main__":
    main()
