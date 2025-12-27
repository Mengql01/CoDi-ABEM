import os
import json
import random
from openai import OpenAI
from datetime import datetime
import concurrent.futures





def process_single_group(i):
    try:
        user1 = f"""
        Generate a 10-zone building model comprising 2 identical floors with 5 zones each, sharing 5.5 m (width) × 4.5 m (height) east-west walls but varying lengths (6.0/6.5/7.0/7.5/8.0 m west-to-east). Each zone contains two 2.4 m (length) × 1.8 m (width) south windows (west edges offset 0.3 m and 3.1 m from wall west edge) and two 2.0 m (length) × 1.4 m (width) north windows (west edges offset 0.7 m and 3.5 m from wall west edge), all having 1.25 m sill height.
        """

        assistant1 = f"""
        "(\"zone01\",\n[(0, 0, 0), (0, 5.5, 0), (6, 5.5, 0), (6, 0, 0), (0, 0, 4.5), (0, 5.5, 4.5), (6, 5.5, 4.5), (6, 0, 4.5)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, ADJ_CEILING, t, zone06\",\n\"s1_e, ADJ_WALL, e, zone02\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (0.3,0,3.05), (0.3,0,1.25), (2.7,0,1.25), (2.7,0,3.05)\",\n\"s1_2, EXT_WINDOW1, s1_s, (3.1,0,3.05), (3.1,0,1.25), (5.5,0,1.25), (5.5,0,3.05)\",\n\"s1_3, EXT_WINDOW1, s1_n, (0.7,5.5,1.25), (0.7,5.5,2.65), (2.7,5.5,2.65), (2.7,5.5,1.25)\",\n\"s1_4, EXT_WINDOW1, s1_n, (3.5,5.5,1.25), (3.5,5.5,2.65), (5.5,5.5,2.65), (5.5,5.5,1.25)\"\n),\n(\"zone02\",\n[(6, 0, 0), (6, 5.5, 0), (12.5, 5.5, 0), (12.5, 0, 0), (6, 0, 4.5), (6, 5.5, 4.5), (12.5, 5.5, 4.5), (12.5, 0, 4.5)],\n\"s2_b, GROUND_FLOOR, b\",\n\"s2_t, ADJ_CEILING, t, zone07\",\n\"s2_e, ADJ_WALL, e, zone03\",\n\"s2_w, ADJ_WALL, w, zone01\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (6.3,0,3.05), (6.3,0,1.25), (8.7,0,1.25), (8.7,0,3.05)\",\n\"s2_2, EXT_WINDOW1, s2_s, (9.1,0,3.05), (9.1,0,1.25), (11.5,0,1.25), (11.5,0,3.05)\",\n\"s2_3, EXT_WINDOW1, s2_n, (6.7,5.5,1.25), (6.7,5.5,2.65), (8.7,5.5,2.65), (8.7,5.5,1.25)\",\n\"s2_4, EXT_WINDOW1, s2_n, (9.5,5.5,1.25), (9.5,5.5,2.65), (11.5,5.5,2.65), (11.5,5.5,1.25)\"\n),\n(\"zone03\",\n[(12.5, 0, 0), (12.5, 5.5, 0), (19.5, 5.5, 0), (19.5, 0, 0), (12.5, 0, 4.5), (12.5, 5.5, 4.5), (19.5, 5.5, 4.5), (19.5, 0, 4.5)],\n\"s3_b, GROUND_FLOOR, b\",\n\"s3_t, ADJ_CEILING, t, zone08\",\n\"s3_e, ADJ_WALL, e, zone04\",\n\"s3_w, ADJ_WALL, w, zone02\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (12.8,0,3.05), (12.8,0,1.25), (15.2,0,1.25), (15.2,0,3.05)\",\n\"s3_2, EXT_WINDOW1, s3_s, (15.6,0,3.05), (15.6,0,1.25), (18,0,1.25), (18,0,3.05)\",\n\"s3_3, EXT_WINDOW1, s3_n, (13.2,5.5,1.25), (13.2,5.5,2.65), (15.2,5.5,2.65), (15.2,5.5,1.25)\",\n\"s3_4, EXT_WINDOW1, s3_n, (16,5.5,1.25), (16,5.5,2.65), (18,5.5,2.65), (18,5.5,1.25)\"\n),\n(\"zone04\",\n[(19.5, 0, 0), (19.5, 5.5, 0), (27, 5.5, 0), (27, 0, 0), (19.5, 0, 4.5), (19.5, 5.5, 4.5), (27, 5.5, 4.5), (27, 0, 4.5)],\n\"s4_b, GROUND_FLOOR, b\",\n\"s4_t, ADJ_CEILING, t, zone09\",\n\"s4_e, ADJ_WALL, e, zone05\",\n\"s4_w, ADJ_WALL, w, zone03\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (19.8,0,3.05), (19.8,0,1.25), (22.2,0,1.25), (22.2,0,3.05)\",\n\"s4_2, EXT_WINDOW1, s4_s, (22.6,0,3.05), (22.6,0,1.25), (25,0,1.25), (25,0,3.05)\",\n\"s4_3, EXT_WINDOW1, s4_n, (20.2,5.5,1.25), (20.2,5.5,2.65), (22.2,5.5,2.65), (22.2,5.5,1.25)\",\n\"s4_4, EXT_WINDOW1, s4_n, (23,5.5,1.25), (23,5.5,2.65), (25,5.5,2.65), (25,5.5,1.25)\"\n),\n(\"zone05\",\n[(27, 0, 0), (27, 5.5, 0), (35, 5.5, 0), (35, 0, 0), (27, 0, 4.5), (27, 5.5, 4.5), (35, 5.5, 4.5), (35, 0, 4.5)],\n\"s5_b, GROUND_FLOOR, b\",\n\"s5_t, ADJ_CEILING, t, zone10\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, ADJ_WALL, w, zone04\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (27.3,0,3.05), (27.3,0,1.25), (29.7,0,1.25), (29.7,0,3.05)\",\n\"s5_2, EXT_WINDOW1, s5_s, (30.1,0,3.05), (30.1,0,1.25), (32.5,0,1.25), (32.5,0,3.05)\",\n\"s5_3, EXT_WINDOW1, s5_n, (27.7,5.5,1.25), (27.7,5.5,2.65), (29.7,5.5,2.65), (29.7,5.5,1.25)\",\n\"s5_4, EXT_WINDOW1, s5_n, (30.5,5.5,1.25), (30.5,5.5,2.65), (32.5,5.5,2.65), (32.5,5.5,1.25)\"\n),\n(\"zone06\",\n[(0, 0, 4.5), (0, 5.5, 4.5), (6, 5.5, 4.5), (6, 0, 4.5), (0, 0, 9), (0, 5.5, 9), (6, 5.5, 9), (6, 0, 9)],\n\"s6_b, ADJ_CEILING, b, zone01\",\n\"s6_t, EXT_ROOF, t\",\n\"s6_e, ADJ_WALL, e, zone07\",\n\"s6_w, EXT_WALL, w\",\n\"s6_n, EXT_WALL, n\",\n\"s6_s, EXT_WALL, s\",\n\"s6_1, EXT_WINDOW1, s6_s, (0.3,0,7.55), (0.3,0,5.75), (2.7,0,5.75), (2.7,0,7.55)\",\n\"s6_2, EXT_WINDOW1, s6_s, (3.1,0,7.55), (3.1,0,5.75), (5.5,0,5.75), (5.5,0,7.55)\",\n\"s6_3, EXT_WINDOW1, s6_n, (0.7,5.5,5.75), (0.7,5.5,7.15), (2.7,5.5,7.15), (2.7,5.5,5.75)\",\n\"s6_4, EXT_WINDOW1, s6_n, (3.5,5.5,5.75), (3.5,5.5,7.15), (5.5,5.5,7.15), (5.5,5.5,5.75)\"\n),\n(\"zone07\",\n[(6, 0, 4.5), (6, 5.5, 4.5), (12.5, 5.5, 4.5), (12.5, 0, 4.5), (6, 0, 9), (6, 5.5, 9), (12.5, 5.5, 9), (12.5, 0, 9)],\n\"s7_b, ADJ_CEILING, b, zone02\",\n\"s7_t, EXT_ROOF, t\",\n\"s7_e, ADJ_WALL, e, zone08\",\n\"s7_w, ADJ_WALL, w, zone06\",\n\"s7_n, EXT_WALL, n\",\n\"s7_s, EXT_WALL, s\",\n\"s7_1, EXT_WINDOW1, s7_s, (6.3,0,7.55), (6.3,0,5.75), (8.7,0,5.75), (8.7,0,7.55)\",\n\"s7_2, EXT_WINDOW1, s7_s, (9.1,0,7.55), (9.1,0,5.75), (11.5,0,5.75), (11.5,0,7.55)\",\n\"s7_3, EXT_WINDOW1, s7_n, (6.7,5.5,5.75), (6.7,5.5,7.15), (8.7,5.5,7.15), (8.7,5.5,5.75)\",\n\"s7_4, EXT_WINDOW1, s7_n, (9.5,5.5,5.75), (9.5,5.5,7.15), (11.5,5.5,7.15), (11.5,5.5,5.75)\"\n),\n(\"zone08\",\n[(12.5, 0, 4.5), (12.5, 5.5, 4.5), (19.5, 5.5, 4.5), (19.5, 0, 4.5), (12.5, 0, 9), (12.5, 5.5, 9), (19.5, 5.5, 9), (19.5, 0, 9)],\n\"s8_b, ADJ_CEILING, b, zone03\",\n\"s8_t, EXT_ROOF, t\",\n\"s8_e, ADJ_WALL, e, zone09\",\n\"s8_w, ADJ_WALL, w, zone07\",\n\"s8_n, EXT_WALL, n\",\n\"s8_s, EXT_WALL, s\",\n\"s8_1, EXT_WINDOW1, s8_s, (12.8,0,7.55), (12.8,0,5.75), (15.2,0,5.75), (15.2,0,7.55)\",\n\"s8_2, EXT_WINDOW1, s8_s, (15.6,0,7.55), (15.6,0,5.75), (18,0,5.75), (18,0,7.55)\",\n\"s8_3, EXT_WINDOW1, s8_n, (13.2,5.5,5.75), (13.2,5.5,7.15), (15.2,5.5,7.15), (15.2,5.5,5.75)\",\n\"s8_4, EXT_WINDOW1, s8_n, (16,5.5,5.75), (16,5.5,7.15), (18,5.5,7.15), (18,5.5,5.75)\"\n),\n(\"zone09\",\n[(19.5, 0, 4.5), (19.5, 5.5, 4.5), (27, 5.5, 4.5), (27, 0, 4.5), (19.5, 0, 9), (19.5, 5.5, 9), (27, 5.5, 9), (27, 0, 9)],\n\"s9_b, ADJ_CEILING, b, zone04\",\n\"s9_t, EXT_ROOF, t\",\n\"s9_e, ADJ_WALL, e, zone10\",\n\"s9_w, ADJ_WALL, w, zone08\",\n\"s9_n, EXT_WALL, n\",\n\"s9_s, EXT_WALL, s\",\n\"s9_1, EXT_WINDOW1, s9_s, (19.8,0,7.55), (19.8,0,5.75), (22.2,0,5.75), (22.2,0,7.55)\",\n\"s9_2, EXT_WINDOW1, s9_s, (22.6,0,7.55), (22.6,0,5.75), (25,0,5.75), (25,0,7.55)\",\n\"s9_3, EXT_WINDOW1, s9_n, (20.2,5.5,5.75), (20.2,5.5,7.15), (22.2,5.5,7.15), (22.2,5.5,5.75)\",\n\"s9_4, EXT_WINDOW1, s9_n, (23,5.5,5.75), (23,5.5,7.15), (25,5.5,7.15), (25,5.5,5.75)\"\n),\n(\"zone10\",\n[(27, 0, 4.5), (27, 5.5, 4.5), (35, 5.5, 4.5), (35, 0, 4.5), (27, 0, 9), (27, 5.5, 9), (35, 5.5, 9), (35, 0, 9)],\n\"s10_b, ADJ_CEILING, b, zone05\",\n\"s10_t, EXT_ROOF, t\",\n\"s10_e, EXT_WALL, e\",\n\"s10_w, ADJ_WALL, w, zone09\",\n\"s10_n, EXT_WALL, n\",\n\"s10_s, EXT_WALL, s\",\n\"s10_1, EXT_WINDOW1, s10_s, (27.3,0,7.55), (27.3,0,5.75), (29.7,0,5.75), (29.7,0,7.55)\",\n\"s10_2, EXT_WINDOW1, s10_s, (30.1,0,7.55), (30.1,0,5.75), (32.5,0,5.75), (32.5,0,7.55)\",\n\"s10_3, EXT_WINDOW1, s10_n, (27.7,5.5,5.75), (27.7,5.5,7.15), (29.7,5.5,7.15), (29.7,5.5,5.75)\",\n\"s10_4, EXT_WINDOW1, s10_n, (30.5,5.5,5.75), (30.5,5.5,7.15), (32.5,5.5,7.15), (32.5,5.5,5.75)\"\n)"
        """
        
        user2 = f"""
        The new task is as follows, please analyze the answer code of sample tasks provided above, then similarly generate the corresponding answer code for the new task. The new task: Generate a 10-zone building model comprising 2 identical floors with 5 zones each, sharing 6.3 m (width) × 6.7 m (height) east-west walls but varying lengths (11.0/7.5/7.1/10.1/11.7 m west-to-east). Each zone contains two 1.9 m (length) × 3.4 m (width) south windows (west edges offset 0.2 m and 3.3 m from wall west edge) and two 2.5 m (length) × 2.3 m (width) north windows (west edges offset 0.3 m and 3.2 m from wall west edge), all having 1.25 m sill height.
        """
        
        
        client = OpenAI(
            api_key=os.environ.get("ARK_API_KEY"),
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )

        stream = client.chat.completions.create(
            model="deepseek-r1-250120",  # your model endpoint ID
            messages=[
                # {"role": "system", "content": ""},
                {"role": "user", "content": user1.strip()},
                {"role": "assistant", "content": assistant1.strip()},
                {"role": "user", "content": user2.strip()}
            ],
            temperature=0.1,
            max_tokens=16384,
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
        total_groups = 1
        max_workers = 1
        current_batch = []
        batch_counter = 0

        # Initialize an empty file
        with open(os.path.splitext(os.path.basename(__file__))[0]+".json", "w", encoding="utf-8") as f:
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
                        with open(os.path.splitext(os.path.basename(__file__))[0]+".json", "r+", encoding="utf-8") as f:
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
            with open(os.path.splitext(os.path.basename(__file__))[0]+".json", "r+", encoding="utf-8") as f:
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
            with open(os.path.splitext(os.path.basename(__file__))[0]+".json", "r+", encoding="utf-8") as f:
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
