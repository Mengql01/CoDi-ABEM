"""
lossless_verification_for_multi-zone_BEM.py
=============================================
Systematic round-trip verification module for BEM prompt compression rules.

This module validates the losslessness of the proposed compression rules across
all 4,000 distillation dataset samples spanning four BEM tasks.

Verification workflow for EACH sample:
    Original compressed text (from dataset)
      -> [Decompression] -> Full IDF text
      -> [Compression]   -> Reconstructed compressed text
      -> [Decompression] -> Reconstructed IDF text
      -> Character-by-character comparison with original IDF text

Usage:
    python lossless_verification_for_multi-zone_BEM.py

Requires:
    - decompression_rules_for_multi-zone_BEM.py (in the same directory)
    - compression_rules_for_multi-zone_BEM.py   (in the same directory)
    - all_4000_compressed_samples.json           (in the same directory)
"""

import json
import os
import sys
import re
import time
import importlib.util

# ---------------------------------------------------------------------------
# 1.  Locate and import the companion compression / decompression modules
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

decompress_path = os.path.join(SCRIPT_DIR, "decompression_rules_for_multi-zone_BEM.py")
compress_path = os.path.join(SCRIPT_DIR, "compression_rules_for_multi-zone_BEM.py")

for p, name in [(decompress_path, "decompression"), (compress_path, "compression")]:
    if not os.path.exists(p):
        print(f"ERROR: {name} module not found at: {p}")
        sys.exit(1)

spec_d = importlib.util.spec_from_file_location("decompress_mod", decompress_path)
decompress_mod = importlib.util.module_from_spec(spec_d)
spec_d.loader.exec_module(decompress_mod)

spec_c = importlib.util.spec_from_file_location("compress_mod", compress_path)
compress_mod = importlib.util.module_from_spec(spec_c)
spec_c.loader.exec_module(compress_mod)

# ---------------------------------------------------------------------------
# 2.  Helper: parse compressed text into zones data structure
# ---------------------------------------------------------------------------

def parse_compressed_text_to_zones(compressed_text):
    """
    Parse the compressed text (Python tuple literal) from a dataset sample
    into the zones list that can be fed to generate_building().

    Handles multiple format variations found in the dataset:
      - With or without outer tuple wrapper
      - With or without ```python``` code fences
      - Various whitespace / indentation styles
      - Inline comments (e.g., # 1st floor)
      - Unevaluated arithmetic expressions (e.g., 7.8+1.25)
      - Ellipsis (...) placeholders
      - Leading zeros in numeric literals
    """
    # Extract content between ```python ... ``` code fences (ignore trailing text)
    text = compressed_text.strip()
    fence_match = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        # Fallback: try simple stripping
        if text.startswith("```python"):
            text = text[len("```python"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    # --- Pre-processing to fix common data quality issues ---

    # Remove inline comments: # ... (but preserve strings)
    # Process line by line, only strip comments outside of quotes
    cleaned_lines = []
    for line in text.split('\n'):
        # Find comment position outside quotes
        in_str = False
        str_char = None
        comment_pos = -1
        for i, ch in enumerate(line):
            if in_str:
                if ch == str_char:
                    in_str = False
            else:
                if ch in ('"', "'"):
                    in_str = True
                    str_char = ch
                elif ch == '#':
                    comment_pos = i
                    break
        if comment_pos >= 0:
            line = line[:comment_pos]
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # Remove ellipsis (...) which some samples use as placeholders
    text = text.replace('...', '')

    # Evaluate simple arithmetic in numeric positions (e.g., 7.8+1.25 → 9.05)
    def eval_arith(m):
        try:
            return str(round(eval(m.group(0)), 6))
        except:
            return m.group(0)
    # Only apply within parentheses context (coordinate tuples), not inside strings
    text = re.sub(r'(?<=[(\[,])\s*(\d+\.?\d*\s*[+\-]\s*\d+\.?\d*)\s*(?=[,)\]])',
                  lambda m: eval_arith(m), text)

    # Fix leading zeros (e.g., 09 → 9)
    text = re.sub(r'(?<=[(\[,\s])0+(\d+\.?\d*)', r'\1', text)

    # Fix double decimals (e.g., 26.00.4 → best effort skip)

    # Wrap in a list to guarantee eval() always produces a sequence of zones.
    wrapped = f"[{text}]"

    try:
        raw = eval(wrapped)
    except Exception as e:
        raise ValueError(f"Failed to parse compressed text: {e}\nText start: {text[:200]}")

    # raw is now a list.  Determine what it contains.
    if len(raw) == 1 and isinstance(raw[0], tuple):
        inner = raw[0]
        if isinstance(inner[0], str):
            zone_tuples = [inner]
        elif isinstance(inner[0], tuple):
            zone_tuples = list(inner)
        else:
            zone_tuples = list(inner)
    else:
        zone_tuples = list(raw)

    # Convert to the format expected by generate_building()
    zones = []
    for zt in zone_tuples:
        zone_name = zt[0]
        vertices = list(zt[1])
        surface_defs = list(zt[2:])
        zones.append((zone_name, vertices, *surface_defs))

    return zones


# ---------------------------------------------------------------------------
# 3.  Core verification function for a single sample
# ---------------------------------------------------------------------------

def verify_single_sample(compressed_text, sample_id="unknown"):
    """
    Perform round-trip verification for a single sample.

    Steps:
        1. Parse compressed text → zones data structure
        2. Decompress: zones → IDF text (original_idf)
        3. Compress:   IDF text → reconstructed zones
        4. Decompress: reconstructed zones → reconstructed IDF text
        5. Compare original_idf vs reconstructed_idf character-by-character

    Returns:
        dict with keys: sample_id, passed, original_len, reconstructed_len,
                        match_rate, num_zones, num_surfaces, num_windows, error
    """
    result = {
        'sample_id': sample_id,
        'passed': False,
        'original_len': 0,
        'reconstructed_len': 0,
        'match_rate': 0.0,
        'num_zones': 0,
        'num_surfaces': 0,
        'num_windows': 0,
        'error': None
    }

    try:
        # Step 1: Parse compressed text
        zones = parse_compressed_text_to_zones(compressed_text)
        result['num_zones'] = len(zones)

        # Count surfaces and windows
        for z in zones:
            for item in z[2:]:  # surface definitions
                if 'EXT_WINDOW1' in item:
                    result['num_windows'] += 1
                else:
                    result['num_surfaces'] += 1

        # Step 2: Decompress → original IDF
        original_idf = decompress_mod.generate_building(zones)
        result['original_len'] = len(original_idf)

        # Step 3: Compress IDF → reconstructed compressed representation
        compressed_zones = compress_mod.compress_building(original_idf)

        # Step 4: Reconstruct zones and decompress again
        reconstructed_zones = []
        for zone_name, vertices_str, surface_defs in compressed_zones:
            vertices = eval(vertices_str)
            plain_defs = [sd.strip('"') for sd in surface_defs]
            zone_tuple = (zone_name, vertices, *plain_defs)
            reconstructed_zones.append(zone_tuple)

        reconstructed_idf = decompress_mod.generate_building(reconstructed_zones)
        result['reconstructed_len'] = len(reconstructed_idf)

        # Step 5: Character-by-character comparison
        if original_idf == reconstructed_idf:
            result['passed'] = True
            result['match_rate'] = 100.0
        else:
            # Calculate match rate
            min_len = min(len(original_idf), len(reconstructed_idf))
            max_len = max(len(original_idf), len(reconstructed_idf))
            matching = sum(1 for a, b in zip(original_idf, reconstructed_idf) if a == b)
            result['match_rate'] = (matching / max_len * 100) if max_len > 0 else 0.0

    except Exception as e:
        result['error'] = str(e)

    return result


# ---------------------------------------------------------------------------
# 4.  Main: load all 4000 samples and run verification
# ---------------------------------------------------------------------------

def load_all_samples(dataset_dir):
    """Load all 4000 samples from the dataset JSON files."""
    all_samples = []

    task_files = {
        1: ("train1.json", "eval1.json"),
        2: ("train2.json", "eval2.json"),
        3: ("train3.json", "eval3.json"),
        4: ("train.json", "eval.json"),
    }

    for task_num in range(1, 5):
        task_dir = os.path.join(dataset_dir, f"distillation dataset_task{task_num}")
        train_file, eval_file = task_files[task_num]

        for split_name, filename in [("train", train_file), ("eval", eval_file)]:
            filepath = os.path.join(task_dir, filename)
            if not os.path.exists(filepath):
                print(f"WARNING: File not found: {filepath}")
                continue

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for i, sample in enumerate(data):
                gpt_value = sample['conversations'][1]['value']
                sample_id = f"task{task_num}_{split_name}_{i+1:04d}"
                all_samples.append({
                    'sample_id': sample_id,
                    'task': task_num,
                    'split': split_name,
                    'compressed_text': gpt_value
                })

    return all_samples


def run_full_verification(dataset_dir, output_dir):
    """Run round-trip verification on all 4000 samples."""

    print("=" * 80)
    print("LOSSLESS COMPRESSION VERIFICATION FOR MULTI-ZONE BEM")
    print("=" * 80)
    print()

    # --- Load samples ---
    print("Loading all 4,000 samples from dataset...")
    all_samples = load_all_samples(dataset_dir)
    print(f"  Loaded {len(all_samples)} samples across 4 tasks.")
    print()

    # --- Save compressed samples JSON (Step 1 of user requirement) ---
    compressed_json_path = os.path.join(output_dir, "all_4000_compressed_samples.json")
    compressed_records = []
    for s in all_samples:
        compressed_records.append({
            'sample_id': s['sample_id'],
            'task': s['task'],
            'split': s['split'],
            'compressed_text': s['compressed_text']
        })
    with open(compressed_json_path, 'w', encoding='utf-8') as f:
        json.dump(compressed_records, f, ensure_ascii=False, indent=2)
    print(f"  Saved compressed samples → {compressed_json_path}")

    # --- Decompress all samples and save (Step 2 of user requirement) ---
    print("Decompressing all 4,000 samples to IDF format...")
    decompressed_records = []
    decompress_errors = []

    for idx, s in enumerate(all_samples):
        try:
            zones = parse_compressed_text_to_zones(s['compressed_text'])
            idf_text = decompress_mod.generate_building(zones)
            decompressed_records.append({
                'sample_id': s['sample_id'],
                'task': s['task'],
                'split': s['split'],
                'idf_text': idf_text
            })
        except Exception as e:
            decompress_errors.append({'sample_id': s['sample_id'], 'error': str(e)})
            decompressed_records.append({
                'sample_id': s['sample_id'],
                'task': s['task'],
                'split': s['split'],
                'idf_text': None,
                'error': str(e)
            })

        if (idx + 1) % 500 == 0:
            print(f"  Decompressed {idx + 1}/{len(all_samples)} samples...")

    decompressed_json_path = os.path.join(output_dir, "all_4000_decompressed_idf.json")
    with open(decompressed_json_path, 'w', encoding='utf-8') as f:
        json.dump(decompressed_records, f, ensure_ascii=False, indent=2)
    print(f"  Saved decompressed IDF files → {decompressed_json_path}")
    if decompress_errors:
        print(f"  WARNING: {len(decompress_errors)} samples failed decompression.")
    print()

    # --- Round-trip verification for each sample (Step 3) ---
    print("Running round-trip verification (IDF → compress → decompress → compare)...")
    print("-" * 80)

    results = []
    passed_count = 0
    failed_count = 0
    error_count = 0
    total_original_chars = 0
    total_reconstructed_chars = 0
    total_zones = 0
    total_surfaces = 0
    total_windows = 0

    task_stats = {t: {'total': 0, 'passed': 0, 'failed': 0} for t in range(1, 5)}

    start_time = time.time()

    for idx, s in enumerate(all_samples):
        r = verify_single_sample(s['compressed_text'], s['sample_id'])
        r['task'] = s['task']
        results.append(r)

        task_stats[s['task']]['total'] += 1

        if r['error']:
            error_count += 1
            task_stats[s['task']]['failed'] += 1
        elif r['passed']:
            passed_count += 1
            task_stats[s['task']]['passed'] += 1
            total_original_chars += r['original_len']
            total_reconstructed_chars += r['reconstructed_len']
            total_zones += r['num_zones']
            total_surfaces += r['num_surfaces']
            total_windows += r['num_windows']
        else:
            failed_count += 1
            task_stats[s['task']]['failed'] += 1

        if (idx + 1) % 500 == 0:
            elapsed = time.time() - start_time
            print(f"  Verified {idx + 1}/{len(all_samples)} samples "
                  f"({passed_count} passed, {failed_count} failed, {error_count} errors) "
                  f"[{elapsed:.1f}s]")

    elapsed = time.time() - start_time
    print(f"  Verified {len(all_samples)}/{len(all_samples)} samples "
          f"({passed_count} passed, {failed_count} failed, {error_count} errors) "
          f"[{elapsed:.1f}s]")
    print()

    # --- Save detailed verification results ---
    verification_json_path = os.path.join(output_dir, "verification_results.json")
    with open(verification_json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Saved per-sample verification results → {verification_json_path}")
    print()

    # --- Print summary report ---
    print("=" * 80)
    print("VERIFICATION SUMMARY REPORT")
    print("=" * 80)
    print()
    print(f"  Total samples verified:          {len(all_samples)}")
    print(f"  Samples PASSED (100% match):     {passed_count}")
    print(f"  Samples FAILED (mismatch):       {failed_count}")
    print(f"  Samples with ERRORS:             {error_count}")
    print(f"  Overall pass rate:               {passed_count / len(all_samples) * 100:.2f}%")
    print()
    print("  Per-task breakdown:")
    for t in range(1, 5):
        ts = task_stats[t]
        rate = ts['passed'] / ts['total'] * 100 if ts['total'] > 0 else 0
        print(f"    Task {t}: {ts['passed']}/{ts['total']} passed ({rate:.2f}%)")
    print()
    print(f"  Total thermal zones verified:    {total_zones}")
    print(f"  Total building surfaces verified:{total_surfaces}")
    print(f"  Total windows verified:          {total_windows}")
    print(f"  Total characters compared:       {total_original_chars:,}")
    print(f"  Character-level match rate:       "
          f"{'100.00%' if passed_count == len(all_samples) else f'{total_original_chars}/{total_reconstructed_chars}'}")
    print()

    if passed_count == len(all_samples):
        print("  *** CONCLUSION: ALL 4,000 SAMPLES PASSED ROUND-TRIP VERIFICATION. ***")
        print("  *** THE PROPOSED COMPRESSION RULES ARE VERIFIED TO BE LOSSLESS.    ***")
    else:
        print("  *** WARNING: Not all samples passed. See verification_results.json ***")

    print()
    print("=" * 80)

    # --- Print any failed samples for debugging ---
    failed_samples = [r for r in results if not r['passed']]
    if failed_samples:
        print("\nFailed/Error samples:")
        for r in failed_samples[:20]:
            print(f"  {r['sample_id']}: match_rate={r['match_rate']:.2f}%, error={r['error']}")

    return passed_count == len(all_samples)


# ---------------------------------------------------------------------------
# 5.  Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dataset_dir = os.path.join(SCRIPT_DIR, "dataset")
    output_dir = SCRIPT_DIR

    # Check if dataset directory exists
    if not os.path.exists(dataset_dir):
        # Try common alternative paths
        alt_paths = [
            "/home/dataset",
            os.path.join(SCRIPT_DIR, "..", "dataset"),
        ]
        for alt in alt_paths:
            if os.path.exists(alt):
                dataset_dir = alt
                break
        else:
            print(f"ERROR: Dataset directory not found.")
            print(f"  Expected at: {dataset_dir}")
            print(f"  Please place the extracted dataset in the same directory as this script.")
            sys.exit(1)

    success = run_full_verification(dataset_dir, output_dir)
    sys.exit(0 if success else 1)
