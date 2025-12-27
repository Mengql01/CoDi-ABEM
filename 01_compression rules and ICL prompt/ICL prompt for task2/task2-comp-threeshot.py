import os
import json
import random
from openai import OpenAI
from datetime import datetime
import concurrent.futures





def process_single_group(i):
    try:
        user1 = f"""
        Generate a 10-zone building model with identical rectangular zones vertically stacked across 10 floors, sharing adjoining floor slabs. Each zone measures 10.7 m (length) × 8.3 m (width) × 4.5 m (height), featuring 8.2 m (length) × 1.8 m (width) windows on both south and north walls with west edges offset 1.1 m from wall west edges, both having 1.25 m sill height.
        """

        assistant1 = f"""
        "(\"zone01\",\n[(0, 0, 0), (0, 8.3, 0), (10.7, 8.3, 0), (10.7, 0, 0), (0, 0, 4.5), (0, 8.3, 4.5), (10.7, 8.3, 4.5), (10.7, 0, 4.5)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, ADJ_CEILING, t, zone02\",\n\"s1_e, EXT_WALL, e\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (1.1,0,3.05), (1.1,0,1.25), (9.3,0,1.25), (9.3,0,3.05)\",\n\"s1_2, EXT_WINDOW1, s1_n, (1.1,8.3,1.25), (1.1,8.3,3.05), (9.3,8.3,3.05), (9.3,8.3,1.25)\"\n),\n(\"zone02\",\n[(0, 0, 4.5), (0, 8.3, 4.5), (10.7, 8.3, 4.5), (10.7, 0, 4.5), (0, 0, 9), (0, 8.3, 9), (10.7, 8.3, 9), (10.7, 0, 9)],\n\"s2_b, ADJ_CEILING, b, zone01\",\n\"s2_t, ADJ_CEILING, t, zone03\",\n\"s2_e, EXT_WALL, e\",\n\"s2_w, EXT_WALL, w\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (1.1,0,7.55), (1.1,0,5.75), (9.3,0,5.75), (9.3,0,7.55)\",\n\"s2_2, EXT_WINDOW1, s2_n, (1.1,8.3,5.75), (1.1,8.3,7.55), (9.3,8.3,7.55), (9.3,8.3,5.75)\"\n),\n(\"zone03\",\n[(0, 0, 9), (0, 8.3, 9), (10.7, 8.3, 9), (10.7, 0, 9), (0, 0, 13.5), (0, 8.3, 13.5), (10.7, 8.3, 13.5), (10.7, 0, 13.5)],\n\"s3_b, ADJ_CEILING, b, zone02\",\n\"s3_t, ADJ_CEILING, t, zone04\",\n\"s3_e, EXT_WALL, e\",\n\"s3_w, EXT_WALL, w\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (1.1,0,12.05), (1.1,0,10.25), (9.3,0,10.25), (9.3,0,12.05)\",\n\"s3_2, EXT_WINDOW1, s3_n, (1.1,8.3,10.25), (1.1,8.3,12.05), (9.3,8.3,12.05), (9.3,8.3,10.25)\"\n),\n(\"zone04\",\n[(0, 0, 13.5), (0, 8.3, 13.5), (10.7, 8.3, 13.5), (10.7, 0, 13.5), (0, 0, 18), (0, 8.3, 18), (10.7, 8.3, 18), (10.7, 0, 18)],\n\"s4_b, ADJ_CEILING, b, zone03\",\n\"s4_t, ADJ_CEILING, t, zone05\",\n\"s4_e, EXT_WALL, e\",\n\"s4_w, EXT_WALL, w\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (1.1,0,16.55), (1.1,0,14.75), (9.3,0,14.75), (9.3,0,16.55)\",\n\"s4_2, EXT_WINDOW1, s4_n, (1.1,8.3,14.75), (1.1,8.3,16.55), (9.3,8.3,16.55), (9.3,8.3,14.75)\"\n),\n(\"zone05\",\n[(0, 0, 18), (0, 8.3, 18), (10.7, 8.3, 18), (10.7, 0, 18), (0, 0, 22.5), (0, 8.3, 22.5), (10.7, 8.3, 22.5), (10.7, 0, 22.5)],\n\"s5_b, ADJ_CEILING, b, zone04\",\n\"s5_t, ADJ_CEILING, t, zone06\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, EXT_WALL, w\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (1.1,0,21.05), (1.1,0,19.25), (9.3,0,19.25), (9.3,0,21.05)\",\n\"s5_2, EXT_WINDOW1, s5_n, (1.1,8.3,19.25), (1.1,8.3,21.05), (9.3,8.3,21.05), (9.3,8.3,19.25)\"\n),\n(\"zone06\",\n[(0, 0, 22.5), (0, 8.3, 22.5), (10.7, 8.3, 22.5), (10.7, 0, 22.5), (0, 0, 27), (0, 8.3, 27), (10.7, 8.3, 27), (10.7, 0, 27)],\n\"s6_b, ADJ_CEILING, b, zone05\",\n\"s6_t, ADJ_CEILING, t, zone07\",\n\"s6_e, EXT_WALL, e\",\n\"s6_w, EXT_WALL, w\",\n\"s6_n, EXT_WALL, n\",\n\"s6_s, EXT_WALL, s\",\n\"s6_1, EXT_WINDOW1, s6_s, (1.1,0,25.55), (1.1,0,23.75), (9.3,0,23.75), (9.3,0,25.55)\",\n\"s6_2, EXT_WINDOW1, s6_n, (1.1,8.3,23.75), (1.1,8.3,25.55), (9.3,8.3,25.55), (9.3,8.3,23.75)\"\n),\n(\"zone07\",\n[(0, 0, 27), (0, 8.3, 27), (10.7, 8.3, 27), (10.7, 0, 27), (0, 0, 31.5), (0, 8.3, 31.5), (10.7, 8.3, 31.5), (10.7, 0, 31.5)],\n\"s7_b, ADJ_CEILING, b, zone06\",\n\"s7_t, ADJ_CEILING, t, zone08\",\n\"s7_e, EXT_WALL, e\",\n\"s7_w, EXT_WALL, w\",\n\"s7_n, EXT_WALL, n\",\n\"s7_s, EXT_WALL, s\",\n\"s7_1, EXT_WINDOW1, s7_s, (1.1,0,30.05), (1.1,0,28.25), (9.3,0,28.25), (9.3,0,30.05)\",\n\"s7_2, EXT_WINDOW1, s7_n, (1.1,8.3,28.25), (1.1,8.3,30.05), (9.3,8.3,30.05), (9.3,8.3,28.25)\"\n),\n(\"zone08\",\n[(0, 0, 31.5), (0, 8.3, 31.5), (10.7, 8.3, 31.5), (10.7, 0, 31.5), (0, 0, 36), (0, 8.3, 36), (10.7, 8.3, 36), (10.7, 0, 36)],\n\"s8_b, ADJ_CEILING, b, zone07\",\n\"s8_t, ADJ_CEILING, t, zone09\",\n\"s8_e, EXT_WALL, e\",\n\"s8_w, EXT_WALL, w\",\n\"s8_n, EXT_WALL, n\",\n\"s8_s, EXT_WALL, s\",\n\"s8_1, EXT_WINDOW1, s8_s, (1.1,0,34.55), (1.1,0,32.75), (9.3,0,32.75), (9.3,0,34.55)\",\n\"s8_2, EXT_WINDOW1, s8_n, (1.1,8.3,32.75), (1.1,8.3,34.55), (9.3,8.3,34.55), (9.3,8.3,32.75)\"\n),\n(\"zone09\",\n[(0, 0, 36), (0, 8.3, 36), (10.7, 8.3, 36), (10.7, 0, 36), (0, 0, 40.5), (0, 8.3, 40.5), (10.7, 8.3, 40.5), (10.7, 0, 40.5)],\n\"s9_b, ADJ_CEILING, b, zone08\",\n\"s9_t, ADJ_CEILING, t, zone10\",\n\"s9_e, EXT_WALL, e\",\n\"s9_w, EXT_WALL, w\",\n\"s9_n, EXT_WALL, n\",\n\"s9_s, EXT_WALL, s\",\n\"s9_1, EXT_WINDOW1, s9_s, (1.1,0,39.05), (1.1,0,37.25), (9.3,0,37.25), (9.3,0,39.05)\",\n\"s9_2, EXT_WINDOW1, s9_n, (1.1,8.3,37.25), (1.1,8.3,39.05), (9.3,8.3,39.05), (9.3,8.3,37.25)\"\n),\n(\"zone10\",\n[(0, 0, 40.5), (0, 8.3, 40.5), (10.7, 8.3, 40.5), (10.7, 0, 40.5), (0, 0, 45), (0, 8.3, 45), (10.7, 8.3, 45), (10.7, 0, 45)],\n\"s10_b, ADJ_CEILING, b, zone09\",\n\"s10_t, EXT_ROOF, t\",\n\"s10_e, EXT_WALL, e\",\n\"s10_w, EXT_WALL, w\",\n\"s10_n, EXT_WALL, n\",\n\"s10_s, EXT_WALL, s\",\n\"s10_1, EXT_WINDOW1, s10_s, (1.1,0,43.55), (1.1,0,41.75), (9.3,0,41.75), (9.3,0,43.55)\",\n\"s10_2, EXT_WINDOW1, s10_n, (1.1,8.3,41.75), (1.1,8.3,43.55), (9.3,8.3,43.55), (9.3,8.3,41.75)\"\n)"
        """

        user2 = f"""
        Generate a 10-zone building model with identical rectangular zones vertically stacked across 10 floors, sharing adjoining floor slabs. Each zone measures 11.3 m (length) × 7.9 m (width) × 5.8 m (height), featuring 7.2 m (length) × 3.0 m (width) windows on both south and north walls with west edges offset 1.1 m from wall west edges, both having 1.25 m sill height.
        """

        assistant2 = f"""
        "(\"zone01\",\n[(0, 0, 0), (0, 7.9, 0), (11.3, 7.9, 0), (11.3, 0, 0), (0, 0, 5.8), (0, 7.9, 5.8), (11.3, 7.9, 5.8), (11.3, 0, 5.8)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, ADJ_CEILING, t, zone02\",\n\"s1_e, EXT_WALL, e\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (1.1,0,4.25), (1.1,0,1.25), (8.3,0,1.25), (8.3,0,4.25)\",\n\"s1_2, EXT_WINDOW1, s1_n, (1.1,7.9,1.25), (1.1,7.9,4.25), (8.3,7.9,4.25), (8.3,7.9,1.25)\"\n),\n(\"zone02\",\n[(0, 0, 5.8), (0, 7.9, 5.8), (11.3, 7.9, 5.8), (11.3, 0, 5.8), (0, 0, 11.6), (0, 7.9, 11.6), (11.3, 7.9, 11.6), (11.3, 0, 11.6)],\n\"s2_b, ADJ_CEILING, b, zone01\",\n\"s2_t, ADJ_CEILING, t, zone03\",\n\"s2_e, EXT_WALL, e\",\n\"s2_w, EXT_WALL, w\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (1.1,0,10.05), (1.1,0,7.05), (8.3,0,7.05), (8.3,0,10.05)\",\n\"s2_2, EXT_WINDOW1, s2_n, (1.1,7.9,7.05), (1.1,7.9,10.05), (8.3,7.9,10.05), (8.3,7.9,7.05)\"\n),\n(\"zone03\",\n[(0, 0, 11.6), (0, 7.9, 11.6), (11.3, 7.9, 11.6), (11.3, 0, 11.6), (0, 0, 17.4), (0, 7.9, 17.4), (11.3, 7.9, 17.4), (11.3, 0, 17.4)],\n\"s3_b, ADJ_CEILING, b, zone02\",\n\"s3_t, ADJ_CEILING, t, zone04\",\n\"s3_e, EXT_WALL, e\",\n\"s3_w, EXT_WALL, w\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (1.1,0,15.85), (1.1,0,12.85), (8.3,0,12.85), (8.3,0,15.85)\",\n\"s3_2, EXT_WINDOW1, s3_n, (1.1,7.9,12.85), (1.1,7.9,15.85), (8.3,7.9,15.85), (8.3,7.9,12.85)\"\n),\n(\"zone04\",\n[(0, 0, 17.4), (0, 7.9, 17.4), (11.3, 7.9, 17.4), (11.3, 0, 17.4), (0, 0, 23.2), (0, 7.9, 23.2), (11.3, 7.9, 23.2), (11.3, 0, 23.2)],\n\"s4_b, ADJ_CEILING, b, zone03\",\n\"s4_t, ADJ_CEILING, t, zone05\",\n\"s4_e, EXT_WALL, e\",\n\"s4_w, EXT_WALL, w\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (1.1,0,21.65), (1.1,0,18.65), (8.3,0,18.65), (8.3,0,21.65)\",\n\"s4_2, EXT_WINDOW1, s4_n, (1.1,7.9,18.65), (1.1,7.9,21.65), (8.3,7.9,21.65), (8.3,7.9,18.65)\"\n),\n(\"zone05\",\n[(0, 0, 23.2), (0, 7.9, 23.2), (11.3, 7.9, 23.2), (11.3, 0, 23.2), (0, 0, 29), (0, 7.9, 29), (11.3, 7.9, 29), (11.3, 0, 29)],\n\"s5_b, ADJ_CEILING, b, zone04\",\n\"s5_t, ADJ_CEILING, t, zone06\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, EXT_WALL, w\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (1.1,0,27.45), (1.1,0,24.45), (8.3,0,24.45), (8.3,0,27.45)\",\n\"s5_2, EXT_WINDOW1, s5_n, (1.1,7.9,24.45), (1.1,7.9,27.45), (8.3,7.9,27.45), (8.3,7.9,24.45)\"\n),\n(\"zone06\",\n[(0, 0, 29), (0, 7.9, 29), (11.3, 7.9, 29), (11.3, 0, 29), (0, 0, 34.8), (0, 7.9, 34.8), (11.3, 7.9, 34.8), (11.3, 0, 34.8)],\n\"s6_b, ADJ_CEILING, b, zone05\",\n\"s6_t, ADJ_CEILING, t, zone07\",\n\"s6_e, EXT_WALL, e\",\n\"s6_w, EXT_WALL, w\",\n\"s6_n, EXT_WALL, n\",\n\"s6_s, EXT_WALL, s\",\n\"s6_1, EXT_WINDOW1, s6_s, (1.1,0,33.25), (1.1,0,30.25), (8.3,0,30.25), (8.3,0,33.25)\",\n\"s6_2, EXT_WINDOW1, s6_n, (1.1,7.9,30.25), (1.1,7.9,33.25), (8.3,7.9,33.25), (8.3,7.9,30.25)\"\n),\n(\"zone07\",\n[(0, 0, 34.8), (0, 7.9, 34.8), (11.3, 7.9, 34.8), (11.3, 0, 34.8), (0, 0, 40.6), (0, 7.9, 40.6), (11.3, 7.9, 40.6), (11.3, 0, 40.6)],\n\"s7_b, ADJ_CEILING, b, zone06\",\n\"s7_t, ADJ_CEILING, t, zone08\",\n\"s7_e, EXT_WALL, e\",\n\"s7_w, EXT_WALL, w\",\n\"s7_n, EXT_WALL, n\",\n\"s7_s, EXT_WALL, s\",\n\"s7_1, EXT_WINDOW1, s7_s, (1.1,0,39.05), (1.1,0,36.05), (8.3,0,36.05), (8.3,0,39.05)\",\n\"s7_2, EXT_WINDOW1, s7_n, (1.1,7.9,36.05), (1.1,7.9,39.05), (8.3,7.9,39.05), (8.3,7.9,36.05)\"\n),\n(\"zone08\",\n[(0, 0, 40.6), (0, 7.9, 40.6), (11.3, 7.9, 40.6), (11.3, 0, 40.6), (0, 0, 46.4), (0, 7.9, 46.4), (11.3, 7.9, 46.4), (11.3, 0, 46.4)],\n\"s8_b, ADJ_CEILING, b, zone07\",\n\"s8_t, ADJ_CEILING, t, zone09\",\n\"s8_e, EXT_WALL, e\",\n\"s8_w, EXT_WALL, w\",\n\"s8_n, EXT_WALL, n\",\n\"s8_s, EXT_WALL, s\",\n\"s8_1, EXT_WINDOW1, s8_s, (1.1,0,44.85), (1.1,0,41.85), (8.3,0,41.85), (8.3,0,44.85)\",\n\"s8_2, EXT_WINDOW1, s8_n, (1.1,7.9,41.85), (1.1,7.9,44.85), (8.3,7.9,44.85), (8.3,7.9,41.85)\"\n),\n(\"zone09\",\n[(0, 0, 46.4), (0, 7.9, 46.4), (11.3, 7.9, 46.4), (11.3, 0, 46.4), (0, 0, 52.2), (0, 7.9, 52.2), (11.3, 7.9, 52.2), (11.3, 0, 52.2)],\n\"s9_b, ADJ_CEILING, b, zone08\",\n\"s9_t, ADJ_CEILING, t, zone10\",\n\"s9_e, EXT_WALL, e\",\n\"s9_w, EXT_WALL, w\",\n\"s9_n, EXT_WALL, n\",\n\"s9_s, EXT_WALL, s\",\n\"s9_1, EXT_WINDOW1, s9_s, (1.1,0,51.05), (1.1,0,48.05), (8.3,0,48.05), (8.3,0,51.05)\",\n\"s9_2, EXT_WINDOW1, s9_n, (1.1,7.9,48.05), (1.1,7.9,51.05), (8.3,7.9,51.05), (8.3,7.9,48.05)\"\n),\n(\"zone10\",\n[(0, 0, 52.2), (0, 7.9, 52.2), (11.3, 7.9, 52.2), (11.3, 0, 52.2), (0, 0, 58), (0, 7.9, 58), (11.3, 7.9, 58), (11.3, 0, 58)],\n\"s10_b, ADJ_CEILING, b, zone09\",\n\"s10_t, EXT_ROOF, t\",\n\"s10_e, EXT_WALL, e\",\n\"s10_w, EXT_WALL, w\",\n\"s10_n, EXT_WALL, n\",\n\"s10_s, EXT_WALL, s\",\n\"s10_1, EXT_WINDOW1, s10_s, (1.1,0,56.45), (1.1,0,53.45), (8.3,0,53.45), (8.3,0,56.45)\",\n\"s10_2, EXT_WINDOW1, s10_n, (1.1,7.9,53.45), (1.1,7.9,56.45), (8.3,7.9,56.45), (8.3,7.9,53.45)\"\n)"
        """

        user3 = f"""
        Generate a 10-zone building model with identical rectangular zones vertically stacked across 10 floors, sharing adjoining floor slabs. Each zone measures 13.2 m (length) × 8.8 m (width) × 8.0 m (height), featuring 7.6 m (length) × 2.5 m (width) windows on both south and north walls with west edges offset 0.2 m from wall west edges, both having 1.25 m sill height.
        """

        assistant3 = f"""
        "(\"zone01\",\n[(0, 0, 0), (0, 8.8, 0), (13.2, 8.8, 0), (13.2, 0, 0), (0, 0, 8), (0, 8.8, 8), (13.2, 8.8, 8), (13.2, 0, 8)],\n\"s1_b, GROUND_FLOOR, b\",\n\"s1_t, ADJ_CEILING, t, zone02\",\n\"s1_e, EXT_WALL, e\",\n\"s1_w, EXT_WALL, w\",\n\"s1_n, EXT_WALL, n\",\n\"s1_s, EXT_WALL, s\",\n\"s1_1, EXT_WINDOW1, s1_s, (0.2,0,3.75), (0.2,0,1.25), (7.8,0,1.25), (7.8,0,3.75)\",\n\"s1_2, EXT_WINDOW1, s1_n, (0.2,8.8,1.25), (0.2,8.8,3.75), (7.8,8.8,3.75), (7.8,8.8,1.25)\"\n),\n(\"zone02\",\n[(0, 0, 8), (0, 8.8, 8), (13.2, 8.8, 8), (13.2, 0, 8), (0, 0, 16), (0, 8.8, 16), (13.2, 8.8, 16), (13.2, 0, 16)],\n\"s2_b, ADJ_CEILING, b, zone01\",\n\"s2_t, ADJ_CEILING, t, zone03\",\n\"s2_e, EXT_WALL, e\",\n\"s2_w, EXT_WALL, w\",\n\"s2_n, EXT_WALL, n\",\n\"s2_s, EXT_WALL, s\",\n\"s2_1, EXT_WINDOW1, s2_s, (0.2,0,11.75), (0.2,0,9.25), (7.8,0,9.25), (7.8,0,11.75)\",\n\"s2_2, EXT_WINDOW1, s2_n, (0.2,8.8,9.25), (0.2,8.8,11.75), (7.8,8.8,11.75), (7.8,8.8,9.25)\"\n),\n(\"zone03\",\n[(0, 0, 16), (0, 8.8, 16), (13.2, 8.8, 16), (13.2, 0, 16), (0, 0, 24), (0, 8.8, 24), (13.2, 8.8, 24), (13.2, 0, 24)],\n\"s3_b, ADJ_CEILING, b, zone02\",\n\"s3_t, ADJ_CEILING, t, zone04\",\n\"s3_e, EXT_WALL, e\",\n\"s3_w, EXT_WALL, w\",\n\"s3_n, EXT_WALL, n\",\n\"s3_s, EXT_WALL, s\",\n\"s3_1, EXT_WINDOW1, s3_s, (0.2,0,19.75), (0.2,0,17.25), (7.8,0,17.25), (7.8,0,19.75)\",\n\"s3_2, EXT_WINDOW1, s3_n, (0.2,8.8,17.25), (0.2,8.8,19.75), (7.8,8.8,19.75), (7.8,8.8,17.25)\"\n),\n(\"zone04\",\n[(0, 0, 24), (0, 8.8, 24), (13.2, 8.8, 24), (13.2, 0, 24), (0, 0, 32), (0, 8.8, 32), (13.2, 8.8, 32), (13.2, 0, 32)],\n\"s4_b, ADJ_CEILING, b, zone03\",\n\"s4_t, ADJ_CEILING, t, zone05\",\n\"s4_e, EXT_WALL, e\",\n\"s4_w, EXT_WALL, w\",\n\"s4_n, EXT_WALL, n\",\n\"s4_s, EXT_WALL, s\",\n\"s4_1, EXT_WINDOW1, s4_s, (0.2,0,27.75), (0.2,0,25.25), (7.8,0,25.25), (7.8,0,27.75)\",\n\"s4_2, EXT_WINDOW1, s4_n, (0.2,8.8,25.25), (0.2,8.8,27.75), (7.8,8.8,27.75), (7.8,8.8,25.25)\"\n),\n(\"zone05\",\n[(0, 0, 32), (0, 8.8, 32), (13.2, 8.8, 32), (13.2, 0, 32), (0, 0, 40), (0, 8.8, 40), (13.2, 8.8, 40), (13.2, 0, 40)],\n\"s5_b, ADJ_CEILING, b, zone04\",\n\"s5_t, ADJ_CEILING, t, zone06\",\n\"s5_e, EXT_WALL, e\",\n\"s5_w, EXT_WALL, w\",\n\"s5_n, EXT_WALL, n\",\n\"s5_s, EXT_WALL, s\",\n\"s5_1, EXT_WINDOW1, s5_s, (0.2,0,35.75), (0.2,0,33.25), (7.8,0,33.25), (7.8,0,35.75)\",\n\"s5_2, EXT_WINDOW1, s5_n, (0.2,8.8,33.25), (0.2,8.8,35.75), (7.8,8.8,35.75), (7.8,8.8,33.25)\"\n),\n(\"zone06\",\n[(0, 0, 40), (0, 8.8, 40), (13.2, 8.8, 40), (13.2, 0, 40), (0, 0, 48), (0, 8.8, 48), (13.2, 8.8, 48), (13.2, 0, 48)],\n\"s6_b, ADJ_CEILING, b, zone05\",\n\"s6_t, ADJ_CEILING, t, zone07\",\n\"s6_e, EXT_WALL, e\",\n\"s6_w, EXT_WALL, w\",\n\"s6_n, EXT_WALL, n\",\n\"s6_s, EXT_WALL, s\",\n\"s6_1, EXT_WINDOW1, s6_s, (0.2,0,43.75), (0.2,0,41.25), (7.8,0,41.25), (7.8,0,43.75)\",\n\"s6_2, EXT_WINDOW1, s6_n, (0.2,8.8,41.25), (0.2,8.8,43.75), (7.8,8.8,43.75), (7.8,8.8,41.25)\"\n),\n(\"zone07\",\n[(0, 0, 48), (0, 8.8, 48), (13.2, 8.8, 48), (13.2, 0, 48), (0, 0, 56), (0, 8.8, 56), (13.2, 8.8, 56), (13.2, 0, 56)],\n\"s7_b, ADJ_CEILING, b, zone06\",\n\"s7_t, ADJ_CEILING, t, zone08\",\n\"s7_e, EXT_WALL, e\",\n\"s7_w, EXT_WALL, w\",\n\"s7_n, EXT_WALL, n\",\n\"s7_s, EXT_WALL, s\",\n\"s7_1, EXT_WINDOW1, s7_s, (0.2,0,51.75), (0.2,0,49.25), (7.8,0,49.25), (7.8,0,51.75)\",\n\"s7_2, EXT_WINDOW1, s7_n, (0.2,8.8,49.25), (0.2,8.8,51.75), (7.8,8.8,51.75), (7.8,8.8,49.25)\"\n),\n(\"zone08\",\n[(0, 0, 56), (0, 8.8, 56), (13.2, 8.8, 56), (13.2, 0, 56), (0, 0, 64), (0, 8.8, 64), (13.2, 8.8, 64), (13.2, 0, 64)],\n\"s8_b, ADJ_CEILING, b, zone07\",\n\"s8_t, ADJ_CEILING, t, zone09\",\n\"s8_e, EXT_WALL, e\",\n\"s8_w, EXT_WALL, w\",\n\"s8_n, EXT_WALL, n\",\n\"s8_s, EXT_WALL, s\",\n\"s8_1, EXT_WINDOW1, s8_s, (0.2,0,59.75), (0.2,0,57.25), (7.8,0,57.25), (7.8,0,59.75)\",\n\"s8_2, EXT_WINDOW1, s8_n, (0.2,8.8,57.25), (0.2,8.8,59.75), (7.8,8.8,59.75), (7.8,8.8,57.25)\"\n),\n(\"zone09\",\n[(0, 0, 64), (0, 8.8, 64), (13.2, 8.8, 64), (13.2, 0, 64), (0, 0, 72), (0, 8.8, 72), (13.2, 8.8, 72), (13.2, 0, 72)],\n\"s9_b, ADJ_CEILING, b, zone08\",\n\"s9_t, ADJ_CEILING, t, zone10\",\n\"s9_e, EXT_WALL, e\",\n\"s9_w, EXT_WALL, w\",\n\"s9_n, EXT_WALL, n\",\n\"s9_s, EXT_WALL, s\",\n\"s9_1, EXT_WINDOW1, s9_s, (0.2,0,67.75), (0.2,0,65.25), (7.8,0,65.25), (7.8,0,67.75)\",\n\"s9_2, EXT_WINDOW1, s9_n, (0.2,8.8,65.25), (0.2,8.8,67.75), (7.8,8.8,67.75), (7.8,8.8,65.25)\"\n),\n(\"zone10\",\n[(0, 0, 72), (0, 8.8, 72), (13.2, 8.8, 72), (13.2, 0, 72), (0, 0, 80), (0, 8.8, 80), (13.2, 8.8, 80), (13.2, 0, 80)],\n\"s10_b, ADJ_CEILING, b, zone09\",\n\"s10_t, EXT_ROOF, t\",\n\"s10_e, EXT_WALL, e\",\n\"s10_w, EXT_WALL, w\",\n\"s10_n, EXT_WALL, n\",\n\"s10_s, EXT_WALL, s\",\n\"s10_1, EXT_WINDOW1, s10_s, (0.2,0,75.75), (0.2,0,73.25), (7.8,0,73.25), (7.8,0,75.75)\",\n\"s10_2, EXT_WINDOW1, s10_n, (0.2,8.8,73.25), (0.2,8.8,75.75), (7.8,8.8,75.75), (7.8,8.8,73.25)\"\n)"
        """

        user4 = f"""
        The new task is as follows, please analyze the answer code of sample tasks provided above, then similarly generate the corresponding answer code for the new task. The new task: Generate a 10-zone building model with identical rectangular zones vertically stacked across 10 floors, sharing adjoining floor slabs. Each zone measures 12.6 m (length) × 10.0 m (width) × 6.7 m (height), featuring 7.5 m (length) × 2.4 m (width) windows on both south and north walls with west edges offset 0.4 m from wall west edges, both having 1.25 m sill height.
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
                {"role": "user", "content": user2.strip()},
                {"role": "assistant", "content": assistant2.strip()},
                {"role": "user", "content": user3.strip()},
                {"role": "assistant", "content": assistant3.strip()},
                {"role": "user", "content": user4.strip()}
            ],
            # temperature=0.1,
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
                {"from": "assistant3", "value": assistant3.strip()},
                {"from": "user4", "value": user4.strip()},
                {"from": "assistant4", "value": gpt_response}
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
