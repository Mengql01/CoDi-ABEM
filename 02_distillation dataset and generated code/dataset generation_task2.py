import os
import json
import random
from openai import OpenAI
from datetime import datetime
import concurrent.futures


def generate_parameters():
    """Random parameters generation"""
    return [
        round(random.uniform(10, 14), 1),
        round(random.uniform(6, 10), 1),
        round(random.uniform(5, 8), 1),
        round(random.uniform(5.5, 8.5), 1),
        round(random.uniform(1, 3.7), 1),
        round(random.uniform(0.1, 1.4), 1)
    ]


def process_single_group(i):
    try:
        params = generate_parameters()
        user1 = f"""
                Generate a 10-zone building model with identical rectangular zones vertically stacked across 10 floors, sharing adjoining floor slabs. Each zone measures 10.7 m (length) × 8.3 m (width) × 4.5 m (height), featuring 8.2 m (length) × 1.8 m (width) windows on both south and north walls with west edges offset 1.1 m from wall west edges, both having 1.25 m sill height.
                """

        assistant1 = f"""
                "(\"zone01\",\n[(0, 0, 0), (0, 8.3, 0), (10.7, 8.3, 0), (10.7, 0, 0), (0, 0, 4.5), (0, 8.3, 4.5), (10.7, 8.3, 4.5), (10.7, 0, 4.5)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, ADJ_CEILING, t, zone02\",\n\"s1_e, EXT_WALL, e\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (1.1,0,3.05), (1.1,0,1.25), (9.3,0,1.25), (9.3,0,3.05)\",\n\"s1_2, EXT_WINDOW1, s1_n, (1.1,8.3,1.25), (1.1,8.3,3.05), (9.3,8.3,3.05), (9.3,8.3,1.25)\"# Note the coordinate - order difference between north and south windows.\n),\n(\"zone02\",\n[(0, 0, 4.5), (0, 8.3, 4.5), (10.7, 8.3, 4.5), (10.7, 0, 4.5), (0, 0, 9), (0, 8.3, 9), (10.7, 8.3, 9), (10.7, 0, 9)],\n\"s2_b, ADJ_CEILING, b, zone01\",\n\"s2_t, ADJ_CEILING, t, zone03\",\n\"s2_e, EXT_WALL, e\",\n\"s2_w, EXT_WALL, w\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (1.1,0,7.55), (1.1,0,5.75), (9.3,0,5.75), (9.3,0,7.55)\",\n\"s2_2, EXT_WINDOW1, s2_n, (1.1,8.3,5.75), (1.1,8.3,7.55), (9.3,8.3,7.55), (9.3,8.3,5.75)\"\n),\n(\"zone03\",\n[(0, 0, 9), (0, 8.3, 9), (10.7, 8.3, 9), (10.7, 0, 9), (0, 0, 13.5), (0, 8.3, 13.5), (10.7, 8.3, 13.5), (10.7, 0, 13.5)],\n\"s3_b, ADJ_CEILING, b, zone02\",\n\"s3_t, ADJ_CEILING, t, zone04\",\n\"s3_e, EXT_WALL, e\",\n\"s3_w, EXT_WALL, w\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (1.1,0,12.05), (1.1,0,10.25), (9.3,0,10.25), (9.3,0,12.05)\",\n\"s3_2, EXT_WINDOW1, s3_n, (1.1,8.3,10.25), (1.1,8.3,12.05), (9.3,8.3,12.05), (9.3,8.3,10.25)\"\n),\n(\"zone04\",\n[(0, 0, 13.5), (0, 8.3, 13.5), (10.7, 8.3, 13.5), (10.7, 0, 13.5), (0, 0, 18), (0, 8.3, 18), (10.7, 8.3, 18), (10.7, 0, 18)],\n\"s4_b, ADJ_CEILING, b, zone03\",\n\"s4_t, ADJ_CEILING, t, zone05\",\n\"s4_e, EXT_WALL, e\",\n\"s4_w, EXT_WALL, w\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (1.1,0,16.55), (1.1,0,14.75), (9.3,0,14.75), (9.3,0,16.55)\",\n\"s4_2, EXT_WINDOW1, s4_n, (1.1,8.3,14.75), (1.1,8.3,16.55), (9.3,8.3,16.55), (9.3,8.3,14.75)\"\n),\n(\"zone05\",\n[(0, 0, 18), (0, 8.3, 18), (10.7, 8.3, 18), (10.7, 0, 18), (0, 0, 22.5), (0, 8.3, 22.5), (10.7, 8.3, 22.5), (10.7, 0, 22.5)],\n\"s5_b, ADJ_CEILING, b, zone04\",\n\"s5_t, ADJ_CEILING, t, zone06\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, EXT_WALL, w\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (1.1,0,21.05), (1.1,0,19.25), (9.3,0,19.25), (9.3,0,21.05)\",\n\"s5_2, EXT_WINDOW1, s5_n, (1.1,8.3,19.25), (1.1,8.3,21.05), (9.3,8.3,21.05), (9.3,8.3,19.25)\"\n),\n(\"zone06\",\n[(0, 0, 22.5), (0, 8.3, 22.5), (10.7, 8.3, 22.5), (10.7, 0, 22.5), (0, 0, 27), (0, 8.3, 27), (10.7, 8.3, 27), (10.7, 0, 27)],\n\"s6_b, ADJ_CEILING, b, zone05\",\n\"s6_t, ADJ_CEILING, t, zone07\",\n\"s6_e, EXT_WALL, e\",\n\"s6_w, EXT_WALL, w\",\n\"s6_n, EXT_WALL, n\",\n\"s6_s, EXT_WALL, s\",\n\"s6_1, EXT_WINDOW1, s6_s, (1.1,0,25.55), (1.1,0,23.75), (9.3,0,23.75), (9.3,0,25.55)\",\n\"s6_2, EXT_WINDOW1, s6_n, (1.1,8.3,23.75), (1.1,8.3,25.55), (9.3,8.3,25.55), (9.3,8.3,23.75)\"\n),\n(\"zone07\",\n[(0, 0, 27), (0, 8.3, 27), (10.7, 8.3, 27), (10.7, 0, 27), (0, 0, 31.5), (0, 8.3, 31.5), (10.7, 8.3, 31.5), (10.7, 0, 31.5)],\n\"s7_b, ADJ_CEILING, b, zone06\",\n\"s7_t, ADJ_CEILING, t, zone08\",\n\"s7_e, EXT_WALL, e\",\n\"s7_w, EXT_WALL, w\",\n\"s7_n, EXT_WALL, n\",\n\"s7_s, EXT_WALL, s\",\n\"s7_1, EXT_WINDOW1, s7_s, (1.1,0,30.05), (1.1,0,28.25), (9.3,0,28.25), (9.3,0,30.05)\",\n\"s7_2, EXT_WINDOW1, s7_n, (1.1,8.3,28.25), (1.1,8.3,30.05), (9.3,8.3,30.05), (9.3,8.3,28.25)\"\n),\n(\"zone08\",\n[(0, 0, 31.5), (0, 8.3, 31.5), (10.7, 8.3, 31.5), (10.7, 0, 31.5), (0, 0, 36), (0, 8.3, 36), (10.7, 8.3, 36), (10.7, 0, 36)],\n\"s8_b, ADJ_CEILING, b, zone07\",\n\"s8_t, ADJ_CEILING, t, zone09\",\n\"s8_e, EXT_WALL, e\",\n\"s8_w, EXT_WALL, w\",\n\"s8_n, EXT_WALL, n\",\n\"s8_s, EXT_WALL, s\",\n\"s8_1, EXT_WINDOW1, s8_s, (1.1,0,34.55), (1.1,0,32.75), (9.3,0,32.75), (9.3,0,34.55)\",\n\"s8_2, EXT_WINDOW1, s8_n, (1.1,8.3,32.75), (1.1,8.3,34.55), (9.3,8.3,34.55), (9.3,8.3,32.75)\"\n),\n(\"zone09\",\n[(0, 0, 36), (0, 8.3, 36), (10.7, 8.3, 36), (10.7, 0, 36), (0, 0, 40.5), (0, 8.3, 40.5), (10.7, 8.3, 40.5), (10.7, 0, 40.5)],\n\"s9_b, ADJ_CEILING, b, zone08\",\n\"s9_t, ADJ_CEILING, t, zone10\",\n\"s9_e, EXT_WALL, e\",\n\"s9_w, EXT_WALL, w\",\n\"s9_n, EXT_WALL, n\",\n\"s9_s, EXT_WALL, s\",\n\"s9_1, EXT_WINDOW1, s9_s, (1.1,0,39.05), (1.1,0,37.25), (9.3,0,37.25), (9.3,0,39.05)\",\n\"s9_2, EXT_WINDOW1, s9_n, (1.1,8.3,37.25), (1.1,8.3,39.05), (9.3,8.3,39.05), (9.3,8.3,37.25)\"\n),\n(\"zone10\",\n[(0, 0, 40.5), (0, 8.3, 40.5), (10.7, 8.3, 40.5), (10.7, 0, 40.5), (0, 0, 45), (0, 8.3, 45), (10.7, 8.3, 45), (10.7, 0, 45)],\n\"s10_b, ADJ_CEILING, b, zone09\",\n\"s10_t, EXT_ROOF, t\",\n\"s10_e, EXT_WALL, e\",\n\"s10_w, EXT_WALL, w\",\n\"s10_n, EXT_WALL, n\",\n\"s10_s, EXT_WALL, s\",\n\"s10_1, EXT_WINDOW1, s10_s, (1.1,0,43.55), (1.1,0,41.75), (9.3,0,41.75), (9.3,0,43.55)\",\n\"s10_2, EXT_WINDOW1, s10_n, (1.1,8.3,41.75), (1.1,8.3,43.55), (9.3,8.3,43.55), (9.3,8.3,41.75)\"\n)"
                """


        user2 = f"""
                The new task is as follows, please analyze the answer code of sample tasks provided above, then similarly generate the corresponding answer code for the new task. The new task: Generate a 10-zone building model with identical rectangular zones vertically stacked across 10 floors, sharing adjoining floor slabs. Each zone measures {params[0]:.3f} m (length) × {params[1]:.3f} m (width) × {params[2]:.3f} m (height), featuring {params[3]:.3f} m (length) × {params[4]:.3f} m (width) windows on both south and north walls with west edges offset {params[5]:.3f} m from wall west edges, both having 1.25 m sill height.
                """


        client = OpenAI(api_key="sk-xxxxxxxxxxxxxxxxxx", base_url="https://api.deepseek.com")

        # client = OpenAI(
        #     api_key=os.environ.get("ARK_API_KEY"),
        #     base_url="https://ark.cn-beijing.volces.com/api/v3",
        # )

        stream = client.chat.completions.create(
            # model="deepseek-r1-250120",  # your model endpoint ID
            model="deepseek-reasoner",
            messages=[
                # {"role": "system", "content": ""},
                {"role": "user", "content": user1.strip()},
                {"role": "assistant", "content": assistant1.strip()},
                {"role": "user", "content": user2.strip()}
            ],
            temperature=0.1,
            max_tokens=8192,
            stream=True
        )

        gpt_response = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                gpt_response += chunk.choices[0].delta.content

        return {
            "conversations": [
                {"from": "user1", "value": user1.strip()},
                {"from": "assistant1", "value": assistant1.strip()},
                {"from": "user2", "value": user2.strip()},
                {"from": "assistant2", "value": gpt_response}
            ]
        }

    except Exception as e:
        print(f"Data generation for group {i + 1} failed: {e}")
        return None


def generate_dataset():
    try:
        total_groups = 1000
        max_workers = 50
        current_batch = []
        batch_counter = 0

        # Initialize an empty file
        with open("train.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_group, i): i for i in range(total_groups)}

            for future in concurrent.futures.as_completed(futures):
                new_data = future.result()
                if new_data:
                    current_batch.append(new_data)
                    batch_counter += 1

                    # Write to file after every max_workers batches
                    if batch_counter % max_workers == 0:
                        with open("train.json", "r+", encoding="utf-8") as f:
                            try:
                                existing_data = json.load(f)
                            except (json.JSONDecodeError, FileNotFoundError):
                                existing_data = []

                            existing_data.extend(current_batch)
                            f.seek(0)
                            f.truncate()
                            json.dump(existing_data, f, ensure_ascii=False, indent=2)
                            current_batch.clear()

                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"[{current_time}] {batch_counter} batches of data saved")

        # Write remaining data
        if current_batch:
            with open("train.json", "r+", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_data.extend(current_batch)
                f.seek(0)
                f.truncate()
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

        return True

    except Exception as e:
        print(f"Global error message: {e}")
        # Try to save the generated data
        if current_batch:
            with open("train.json", "r+", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_data.extend(current_batch)
                f.seek(0)
                f.truncate()
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
        return False


if __name__ == "__main__":
    success = generate_dataset()
    if success:
        print("All data generated and saved successfully!")
    else:
        print("Data generation failed midway, already saved the generated data!")
