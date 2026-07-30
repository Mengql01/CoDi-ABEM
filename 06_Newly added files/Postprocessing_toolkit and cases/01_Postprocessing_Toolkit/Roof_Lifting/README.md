# Roof Lifting

`roof_lift_idf.py` modifies top geometry to create shed, gable, and local-gable roofs. The distributed Task-08 result for each baseline task contains five roof styles identified by object prefixes `R01` through `R05`.

Use the optional `--report` argument to write validation results. The checks cover duplicate object names, non-planar roof/wall surfaces, empty vertex lists, and incorrect roof normals.
