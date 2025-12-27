import os
import json
import random
from openai import OpenAI
from datetime import datetime
import concurrent.futures


def generate_parameters():
    """Random parameters generation"""
    return [
        round(random.uniform(5, 8), 1),
        round(random.uniform(4, 6), 1),
        round(random.uniform(5, 8), 1),
        round(random.uniform(1.6, 3.6), 1),
        round(random.uniform(1, 3.7), 1),
        round(random.uniform(0.1, 1.2), 1)
    ]


def process_single_group(i):
    try:
        params = generate_parameters()

        user1 = f"""
                Generate a 5-zone building model with identical rectangular zones sharing adjoining east-west walls. Each zone measures 5.0 m (length) × 4.0 m (width) × 4.5 m (height), featuring 3.2 m (length) × 1.8 m (width) windows on both south and north walls with west edges offset 1.1 m from wall west edges, both having 1.25 m sill height.
                """

        assistant1 = f"""
                "(\"zone01\",\n[(0, 0, 0), (0, 4, 0), (5, 4, 0), (5, 0, 0), (0, 0, 4.5), (0, 4, 4.5), (5, 4, 4.5), (5, 0, 4.5)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, EXT_ROOF, t\",\n\"s1_e, ADJ_WALL, e, zone02\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (1.1,0,3.05), (1.1,0,1.25), (4.3,0,1.25), (4.3,0,3.05)\",\n\"s1_2, EXT_WINDOW1, s1_n, (1.1,4,1.25), (1.1,4,3.05), (4.3,4,3.05), (4.3,4,1.25)\"# Note the coordinate - order difference between north and south windows.\n),\n(\"zone02\",\n[(5, 0, 0), (5, 4, 0), (10, 4, 0), (10, 0, 0), (5, 0, 4.5), (5, 4, 4.5), (10, 4, 4.5), (10, 0, 4.5)],\n\"s2_b, GROUND_FLOOR, b\",\n\"s2_t, EXT_ROOF, t\",\n\"s2_e, ADJ_WALL, e, zone03\",\n\"s2_w, ADJ_WALL, w, zone01\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (6.1,0,3.05), (6.1,0,1.25), (9.3,0,1.25), (9.3,0,3.05)\",\n\"s2_2, EXT_WINDOW1, s2_n, (6.1,4,1.25), (6.1,4,3.05), (9.3,4,3.05), (9.3,4,1.25)\"\n),\n(\"zone03\",\n[(10, 0, 0), (10, 4, 0), (15, 4, 0), (15, 0, 0), (10, 0, 4.5), (10, 4, 4.5), (15, 4, 4.5), (15, 0, 4.5)],\n\"s3_b, GROUND_FLOOR, b\",\n\"s3_t, EXT_ROOF, t\",\n\"s3_e, ADJ_WALL, e, zone04\",\n\"s3_w, ADJ_WALL, w, zone02\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (11.1,0,3.05), (11.1,0,1.25), (14.3,0,1.25), (14.3,0,3.05)\",\n\"s3_2, EXT_WINDOW1, s3_n, (11.1,4,1.25), (11.1,4,3.05), (14.3,4,3.05), (14.3,4,1.25)\"\n),\n(\"zone04\",\n[(15, 0, 0), (15, 4, 0), (20, 4, 0), (20, 0, 0), (15, 0, 4.5), (15, 4, 4.5), (20, 4, 4.5), (20, 0, 4.5)],\n\"s4_b, GROUND_FLOOR, b\",\n\"s4_t, EXT_ROOF, t\",\n\"s4_e, ADJ_WALL, e, zone05\",\n\"s4_w, ADJ_WALL, w, zone03\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (16.1,0,3.05), (16.1,0,1.25), (19.3,0,1.25), (19.3,0,3.05)\",\n\"s4_2, EXT_WINDOW1, s4_n, (16.1,4,1.25), (16.1,4,3.05), (19.3,4,3.05), (19.3,4,1.25)\"\n),\n(\"zone05\",\n[(20, 0, 0), (20, 4, 0), (25, 4, 0), (25, 0, 0), (20, 0, 4.5), (20, 4, 4.5), (25, 4, 4.5), (25, 0, 4.5)],\n\"s5_b, GROUND_FLOOR, b\",\n\"s5_t, EXT_ROOF, t\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, ADJ_WALL, w, zone04\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (21.1,0,3.05), (21.1,0,1.25), (24.3,0,1.25), (24.3,0,3.05)\",\n\"s5_2, EXT_WINDOW1, s5_n, (21.1,4,1.25), (21.1,4,3.05), (24.3,4,3.05), (24.3,4,1.25)\"\n)"
                 """


        user2 = f"""
                The new task is as follows, please analyze the answer code of sample tasks provided above, then similarly generate the corresponding answer code for the new task. The new task: Generate a 5-zone building model with identical rectangular zones sharing adjoining east-west walls. Each zone measures {params[0]:.3f} m (length) × {params[1]:.3f} m (width) × {params[2]:.3f} m (height), featuring {params[3]:.3f} m (length) × {params[4]:.3f} m (width) windows on both south and north walls with west edges offset {params[5]:.3f} m from wall west edges, both having 1.25 m sill height.
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
