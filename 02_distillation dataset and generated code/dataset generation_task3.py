import os
import json
import random
from openai import OpenAI
from datetime import datetime
import concurrent.futures


def generate_parameters():
    """Random parameters generation"""
    return [
        round(random.uniform(7, 12), 1),
        round(random.uniform(5, 10), 1),
        round(random.uniform(5, 8), 1),
        round(random.uniform(3, 5.6), 1),
        round(random.uniform(1, 3.7), 1),
        round(random.uniform(0.3, 1.3), 1),
        round(random.uniform(3, 5.6), 1),
        round(random.uniform(1, 3.7), 1),
        round(random.uniform(0.3, 1.3), 1)
    ]


def process_single_group(i):
    try:
        params = generate_parameters()
        user1 = f"""
                Generate a 10-zone building model comprising 2 identical floors with 5 zones each, sharing adjoining east-west walls. Each zone measures 7.6 m (length) × 5.7 m (width) × 4.8 m (height), featuring a 4.7 m (length) × 2.3 m (width) south window (west edge offset 0.7 m from wall west edge) and a 2.9 m (length) × 1.8 m (width) north window (west edge offset 1.3 m from wall west edge), both having 1.25 m sill height.
                """

        assistant1 = f"""
                "(\"zone01\",  # 1st floor\n[(0, 0, 0), (0, 5.7, 0), (7.6, 5.7, 0), (7.6, 0, 0), (0, 0, 4.8), (0, 5.7, 4.8), (7.6, 5.7, 4.8), (7.6, 0, 4.8)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, ADJ_CEILING, t, zone06\",\n\"s1_e, ADJ_WALL, e, zone02\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (0.7,0,3.55), (0.7,0,1.25), (5.4,0,1.25), (5.4,0,3.55)\",\n\"s1_2, EXT_WINDOW1, s1_n, (1.3,5.7,1.25), (1.3,5.7,3.05), (4.2,5.7,3.05), (4.2,5.7,1.25)\"# Note the coordinate - order difference between north and south windows.\n),\n(\"zone02\",\n[(7.6, 0, 0), (7.6, 5.7, 0), (15.2, 5.7, 0), (15.2, 0, 0), (7.6, 0, 4.8), (7.6, 5.7, 4.8), (15.2, 5.7, 4.8), (15.2, 0, 4.8)],\n\"s2_b, GROUND_FLOOR, b\",\n\"s2_t, ADJ_CEILING, t, zone07\",\n\"s2_e, ADJ_WALL, e, zone03\",\n\"s2_w, ADJ_WALL, w, zone01\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (8.3,0,3.55), (8.3,0,1.25), (13,0,1.25), (13,0,3.55)\",\n\"s2_2, EXT_WINDOW1, s2_n, (8.9,5.7,1.25), (8.9,5.7,3.05), (11.8,5.7,3.05), (11.8,5.7,1.25)\"\n),\n(\"zone03\",\n[(15.2, 0, 0), (15.2, 5.7, 0), (22.8, 5.7, 0), (22.8, 0, 0), (15.2, 0, 4.8), (15.2, 5.7, 4.8), (22.8, 5.7, 4.8), (22.8, 0, 4.8)],\n\"s3_b, GROUND_FLOOR, b\",\n\"s3_t, ADJ_CEILING, t, zone08\",\n\"s3_e, ADJ_WALL, e, zone04\",\n\"s3_w, ADJ_WALL, w, zone02\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (15.9,0,3.55), (15.9,0,1.25), (20.6,0,1.25), (20.6,0,3.55)\",\n\"s3_2, EXT_WINDOW1, s3_n, (16.5,5.7,1.25), (16.5,5.7,3.05), (19.4,5.7,3.05), (19.4,5.7,1.25)\"\n),\n(\"zone04\",\n[(22.8, 0, 0), (22.8, 5.7, 0), (30.4, 5.7, 0), (30.4, 0, 0), (22.8, 0, 4.8), (22.8, 5.7, 4.8), (30.4, 5.7, 4.8), (30.4, 0, 4.8)],\n\"s4_b, GROUND_FLOOR, b\",\n\"s4_t, ADJ_CEILING, t, zone09\",\n\"s4_e, ADJ_WALL, e, zone05\",\n\"s4_w, ADJ_WALL, w, zone03\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (23.5,0,3.55), (23.5,0,1.25), (28.2,0,1.25), (28.2,0,3.55)\",\n\"s4_2, EXT_WINDOW1, s4_n, (24.1,5.7,1.25), (24.1,5.7,3.05), (27,5.7,3.05), (27,5.7,1.25)\"\n),\n(\"zone05\",\n[(30.4, 0, 0), (30.4, 5.7, 0), (38, 5.7, 0), (38, 0, 0), (30.4, 0, 4.8), (30.4, 5.7, 4.8), (38, 5.7, 4.8), (38, 0, 4.8)],\n\"s5_b, GROUND_FLOOR, b\",\n\"s5_t, ADJ_CEILING, t, zone10\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, ADJ_WALL, w, zone04\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (31.1,0,3.55), (31.1,0,1.25), (35.8,0,1.25), (35.8,0,3.55)\",\n\"s5_2, EXT_WINDOW1, s5_n, (31.7,5.7,1.25), (31.7,5.7,3.05), (34.6,5.7,3.05), (34.6,5.7,1.25)\"\n),\n(\"zone06\",  # 2nd floor\n[(0, 0, 4.8), (0, 5.7, 4.8), (7.6, 5.7, 4.8), (7.6, 0, 4.8), (0, 0, 9.6), (0, 5.7, 9.6), (7.6, 5.7, 9.6), (7.6, 0, 9.6)],\n\"s6_b, ADJ_CEILING, b, zone01\",\n\"s6_t, EXT_ROOF, t\",\n\"s6_e, ADJ_WALL, e, zone07\",\n\"s6_w, EXT_WALL, w\",\n\"s6_n, EXT_WALL, n\",\n\"s6_s, EXT_WALL, s\",\n\"s6_1, EXT_WINDOW1, s6_s, (0.7,0,8.35), (0.7,0,6.05), (5.4,0,6.05), (5.4,0,8.35)\",\n\"s6_2, EXT_WINDOW1, s6_n, (1.3,5.7,6.05), (1.3,5.7,7.85), (4.2,5.7,7.85), (4.2,5.7,6.05)\"\n),\n(\"zone07\",\n[(7.6, 0, 4.8), (7.6, 5.7, 4.8), (15.2, 5.7, 4.8), (15.2, 0, 4.8), (7.6, 0, 9.6), (7.6, 5.7, 9.6), (15.2, 5.7, 9.6), (15.2, 0, 9.6)],\n\"s7_b, ADJ_CEILING, b, zone02\",\n\"s7_t, EXT_ROOF, t\",\n\"s7_e, ADJ_WALL, e, zone08\",\n\"s7_w, ADJ_WALL, w, zone06\",\n\"s7_n, EXT_WALL, n\",\n\"s7_s, EXT_WALL, s\",\n\"s7_1, EXT_WINDOW1, s7_s, (8.3,0,8.35), (8.3,0,6.05), (13,0,6.05), (13,0,8.35)\",\n\"s7_2, EXT_WINDOW1, s7_n, (8.9,5.7,6.05), (8.9,5.7,7.85), (11.8,5.7,7.85), (11.8,5.7,6.05)\"\n),\n(\"zone08\",\n[(15.2, 0, 4.8), (15.2, 5.7, 4.8), (22.8, 5.7, 4.8), (22.8, 0, 4.8), (15.2, 0, 9.6), (15.2, 5.7, 9.6), (22.8, 5.7, 9.6), (22.8, 0, 9.6)],\n\"s8_b, ADJ_CEILING, b, zone03\",\n\"s8_t, EXT_ROOF, t\",\n\"s8_e, ADJ_WALL, e, zone09\",\n\"s8_w, ADJ_WALL, w, zone07\",\n\"s8_n, EXT_WALL, n\",\n\"s8_s, EXT_WALL, s\",\n\"s8_1, EXT_WINDOW1, s8_s, (15.9,0,8.35), (15.9,0,6.05), (20.6,0,6.05), (20.6,0,8.35)\",\n\"s8_2, EXT_WINDOW1, s8_n, (16.5,5.7,6.05), (16.5,5.7,7.85), (19.4,5.7,7.85), (19.4,5.7,6.05)\"\n),\n(\"zone09\",\n[(22.8, 0, 4.8), (22.8, 5.7, 4.8), (30.4, 5.7, 4.8), (30.4, 0, 4.8), (22.8, 0, 9.6), (22.8, 5.7, 9.6), (30.4, 5.7, 9.6), (30.4, 0, 9.6)],\n\"s9_b, ADJ_CEILING, b, zone04\",\n\"s9_t, EXT_ROOF, t\",\n\"s9_e, ADJ_WALL, e, zone10\",\n\"s9_w, ADJ_WALL, w, zone08\",\n\"s9_n, EXT_WALL, n\",\n\"s9_s, EXT_WALL, s\",\n\"s9_1, EXT_WINDOW1, s9_s, (23.5,0,8.35), (23.5,0,6.05), (28.2,0,6.05), (28.2,0,8.35)\",\n\"s9_2, EXT_WINDOW1, s9_n, (24.1,5.7,6.05), (24.1,5.7,7.85), (27,5.7,7.85), (27,5.7,6.05)\"\n),\n(\"zone10\",\n[(30.4, 0, 4.8), (30.4, 5.7, 4.8), (38, 5.7, 4.8), (38, 0, 4.8), (30.4, 0, 9.6), (30.4, 5.7, 9.6), (38, 5.7, 9.6), (38, 0, 9.6)],\n\"s10_b, ADJ_CEILING, b, zone05\",\n\"s10_t, EXT_ROOF, t\",\n\"s10_e, EXT_WALL, e\",\n\"s10_w, ADJ_WALL, w, zone09\",\n\"s10_n, EXT_WALL, n\",\n\"s10_s, EXT_WALL, s\",\n\"s10_1, EXT_WINDOW1, s10_s, (31.1,0,8.35), (31.1,0,6.05), (35.8,0,6.05), (35.8,0,8.35)\",\n\"s10_2, EXT_WINDOW1, s10_n, (31.7,5.7,6.05), (31.7,5.7,7.85), (34.6,5.7,7.85), (34.6,5.7,6.05)\"\n)"
                """


        user2 = f"""
                The new task is as follows, please analyze the answer code of sample tasks provided above, then similarly generate the corresponding answer code for the new task. The new task: Generate a 10-zone building model comprising 2 identical floors with 5 zones each, sharing adjoining east-west walls. Each zone measures {params[0]:.3f} m (length) × {params[1]:.3f} m (width) × {params[2]:.3f} m (height), featuring a {params[3]:.3f} m (length) × {params[4]:.3f} m (width) south window (west edge offset {params[5]:.3f} m from wall west edge) and a {params[6]:.3f} m (length) × {params[7]:.3f} m (width) north window (west edge offset {params[8]:.3f} m from wall west edge), both having 1.25 m sill height.
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
