import os
import json
import random
from openai import OpenAI
from datetime import datetime
import concurrent.futures





def process_single_group(i):
    try:
        user1 = f"""
        Generate a 5-zone building model with identical rectangular zones sharing adjoining east-west walls. Each zone measures 5.0 m (length) × 4.0 m (width) × 4.5 m (height), featuring 3.2 m (length) × 1.8 m (width) windows on both south and north walls with west edges offset 1.1 m from wall west edges, both having 1.25 m sill height.
        """

        assistant1 = f"""
        "(\"zone01\",\n[(0, 0, 0), (0, 4, 0), (5, 4, 0), (5, 0, 0), (0, 0, 4.5), (0, 4, 4.5), (5, 4, 4.5), (5, 0, 4.5)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, EXT_ROOF, t\",\n\"s1_e, ADJ_WALL, e, zone02\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (1.1,0,3.05), (1.1,0,1.25), (4.3,0,1.25), (4.3,0,3.05)\",\n\"s1_2, EXT_WINDOW1, s1_n, (1.1,4,1.25), (1.1,4,3.05), (4.3,4,3.05), (4.3,4,1.25)\"\n),\n(\"zone02\",\n[(5, 0, 0), (5, 4, 0), (10, 4, 0), (10, 0, 0), (5, 0, 4.5), (5, 4, 4.5), (10, 4, 4.5), (10, 0, 4.5)],\n\"s2_b, GROUND_FLOOR, b\",\n\"s2_t, EXT_ROOF, t\",\n\"s2_e, ADJ_WALL, e, zone03\",\n\"s2_w, ADJ_WALL, w, zone01\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (6.1,0,3.05), (6.1,0,1.25), (9.3,0,1.25), (9.3,0,3.05)\",\n\"s2_2, EXT_WINDOW1, s2_n, (6.1,4,1.25), (6.1,4,3.05), (9.3,4,3.05), (9.3,4,1.25)\"\n),\n(\"zone03\",\n[(10, 0, 0), (10, 4, 0), (15, 4, 0), (15, 0, 0), (10, 0, 4.5), (10, 4, 4.5), (15, 4, 4.5), (15, 0, 4.5)],\n\"s3_b, GROUND_FLOOR, b\",\n\"s3_t, EXT_ROOF, t\",\n\"s3_e, ADJ_WALL, e, zone04\",\n\"s3_w, ADJ_WALL, w, zone02\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (11.1,0,3.05), (11.1,0,1.25), (14.3,0,1.25), (14.3,0,3.05)\",\n\"s3_2, EXT_WINDOW1, s3_n, (11.1,4,1.25), (11.1,4,3.05), (14.3,4,3.05), (14.3,4,1.25)\"\n),\n(\"zone04\",\n[(15, 0, 0), (15, 4, 0), (20, 4, 0), (20, 0, 0), (15, 0, 4.5), (15, 4, 4.5), (20, 4, 4.5), (20, 0, 4.5)],\n\"s4_b, GROUND_FLOOR, b\",\n\"s4_t, EXT_ROOF, t\",\n\"s4_e, ADJ_WALL, e, zone05\",\n\"s4_w, ADJ_WALL, w, zone03\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (16.1,0,3.05), (16.1,0,1.25), (19.3,0,1.25), (19.3,0,3.05)\",\n\"s4_2, EXT_WINDOW1, s4_n, (16.1,4,1.25), (16.1,4,3.05), (19.3,4,3.05), (19.3,4,1.25)\"\n),\n(\"zone05\",\n[(20, 0, 0), (20, 4, 0), (25, 4, 0), (25, 0, 0), (20, 0, 4.5), (20, 4, 4.5), (25, 4, 4.5), (25, 0, 4.5)],\n\"s5_b, GROUND_FLOOR, b\",\n\"s5_t, EXT_ROOF, t\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, ADJ_WALL, w, zone04\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (21.1,0,3.05), (21.1,0,1.25), (24.3,0,1.25), (24.3,0,3.05)\",\n\"s5_2, EXT_WINDOW1, s5_n, (21.1,4,1.25), (21.1,4,3.05), (24.3,4,3.05), (24.3,4,1.25)\"\n)"
        """
        
        user2 = f"""
        Generate a 5-zone building model with identical rectangular zones sharing adjoining east-west walls. Each zone measures 5.3 m (length) × 5.6 m (width) × 5.7 m (height), featuring 2.8 m (length) × 3.1 m (width) windows on both south and north walls with west edges offset 0.3 m from wall west edges, both having 1.25 m sill height.
        """

        assistant2 = f"""
        "(\"zone01\",\n[(0, 0, 0), (0, 5.6, 0), (5.3, 5.6, 0), (5.3, 0, 0), (0, 0, 5.7), (0, 5.6, 5.7), (5.3, 5.6, 5.7), (5.3, 0, 5.7)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, EXT_ROOF, t\",\n\"s1_e, ADJ_WALL, e, zone02\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (0.3,0,4.35), (0.3,0,1.25), (3.1,0,1.25), (3.1,0,4.35)\",\n\"s1_2, EXT_WINDOW1, s1_n, (0.3,5.6,1.25), (0.3,5.6,4.35), (3.1,5.6,4.35), (3.1,5.6,1.25)\"\n),\n(\"zone02\",\n[(5.3, 0, 0), (5.3, 5.6, 0), (10.6, 5.6, 0), (10.6, 0, 0), (5.3, 0, 5.7), (5.3, 5.6, 5.7), (10.6, 5.6, 5.7), (10.6, 0, 5.7)],\n\"s2_b, GROUND_FLOOR, b\",\n\"s2_t, EXT_ROOF, t\",\n\"s2_e, ADJ_WALL, e, zone03\",\n\"s2_w, ADJ_WALL, w, zone01\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (5.6,0,4.35), (5.6,0,1.25), (8.4,0,1.25), (8.4,0,4.35)\",\n\"s2_2, EXT_WINDOW1, s2_n, (5.6,5.6,1.25), (5.6,5.6,4.35), (8.4,5.6,4.35), (8.4,5.6,1.25)\"\n),\n(\"zone03\",\n[(10.6, 0, 0), (10.6, 5.6, 0), (15.9, 5.6, 0), (15.9, 0, 0), (10.6, 0, 5.7), (10.6, 5.6, 5.7), (15.9, 5.6, 5.7), (15.9, 0, 5.7)],\n\"s3_b, GROUND_FLOOR, b\",\n\"s3_t, EXT_ROOF, t\",\n\"s3_e, ADJ_WALL, e, zone04\",\n\"s3_w, ADJ_WALL, w, zone02\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (10.9,0,4.35), (10.9,0,1.25), (13.7,0,1.25), (13.7,0,4.35)\",\n\"s3_2, EXT_WINDOW1, s3_n, (10.9,5.6,1.25), (10.9,5.6,4.35), (13.7,5.6,4.35), (13.7,5.6,1.25)\"\n),\n(\"zone04\",\n[(15.9, 0, 0), (15.9, 5.6, 0), (21.2, 5.6, 0), (21.2, 0, 0), (15.9, 0, 5.7), (15.9, 5.6, 5.7), (21.2, 5.6, 5.7), (21.2, 0, 5.7)],\n\"s4_b, GROUND_FLOOR, b\",\n\"s4_t, EXT_ROOF, t\",\n\"s4_e, ADJ_WALL, e, zone05\",\n\"s4_w, ADJ_WALL, w, zone03\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (16.2,0,4.35), (16.2,0,1.25), (19.0,0,1.25), (19.0,0,4.35)\",\n\"s4_2, EXT_WINDOW1, s4_n, (16.2,5.6,1.25), (16.2,5.6,4.35), (19.0,5.6,4.35), (19.0,5.6,1.25)\"\n),\n(\"zone05\",\n[(21.2, 0, 0), (21.2, 5.6, 0), (26.5, 5.6, 0), (26.5, 0, 0), (21.2, 0, 5.7), (21.2, 5.6, 5.7), (26.5, 5.6, 5.7), (26.5, 0, 5.7)],\n\"s5_b, GROUND_FLOOR, b\",\n\"s5_t, EXT_ROOF, t\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, ADJ_WALL, w, zone04\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (21.5,0,4.35), (21.5,0,1.25), (24.3,0,1.25), (24.3,0,4.35)\",\n\"s5_2, EXT_WINDOW1, s5_n, (21.5,5.6,1.25), (21.5,5.6,4.35), (24.3,5.6,4.35), (24.3,5.6,1.25)\"\n)"
        """

        user3 = f"""
        The new task is as follows, please analyze the answer code of sample tasks provided above, then similarly generate the corresponding answer code for the new task. The new task: Generate a 5-zone building model with identical rectangular zones sharing adjoining east-west walls. Each zone measures 7.9 m (length) × 4.6 m (width) × 7.5 m (height), featuring 2.5 m (length) × 1.7 m (width) windows on both south and north walls with west edges offset 0.9 m from wall west edges, both having 1.25 m sill height.
        """

        client = OpenAI(
            api_key=os.environ.get("ARK_API_KEY"),
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
        # Here, switch model by updating API-key.
        # "models options": [
        #     "ChatGLM3-6B", "Doubao-1.5-lite-32k", "Ministral-8B-Instruct-2410",
        #     "Mistral-7B-Instruct-v0.2", "Mistral-Small-24B-Base-2501",
        #     "Mistral-Large-Instruct-2407", "Llama-3.1-8B-Instruct",
        #     "Llama-3.1-405B-Instruct", "Qwen2.5-7B-Instruct-1M",
        #     "Qwen2.5-7B-Instruct", "Qwen2.5-14B-Instruct",
        #     "Qwen2.5-Max-250125", "DeepSeek-R1-Distill-Qwen-7B",
        #     "DeepSeek-R1-Distill-Qwen-14B", "DeepSeek-R1-Distill-Qwen-32B",
        #     "DeepSeek-V3-241226", "DeepSeek-R1-250120"
        # ]
        stream = client.chat.completions.create(
            model="deepseek-r1-250120",  # your model endpoint ID
            messages=[
                # {"role": "system", "content": ""},
                {"role": "user", "content": user1.strip()},
                {"role": "assistant", "content": assistant1.strip()},
                {"role": "user", "content": user2.strip()},
                {"role": "assistant", "content": assistant2.strip()},
                {"role": "user", "content": user3.strip()}
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
                {"from": "assistant2", "value": assistant2.strip()},
                {"from": "user3", "value": user3.strip()},
                {"from": "assistant3", "value": gpt_response}
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
