"""Slicer Python Script Generator.

Synthesizes clean, reproducible, idiomatic 3D Slicer Python scripts from validated WorkflowPlans.
"""

from typing import Dict, Any, Optional
import os
import json

from core.workflow import WorkflowPlan


class SlicerCodeGenerator:
    """Translates a WorkflowPlan into standard 3D Slicer Python commands."""

    @classmethod
    def generate_slicer_script(
        cls,
        plan: WorkflowPlan,
        input_file_path: str,
        output_dir: str,
        export_mesh_name: str = "reconstructed_anatomy.stl"
    ) -> str:
        escaped_input = input_file_path.replace("\\", "/")
        escaped_out_dir = output_dir.replace("\\", "/")
        escaped_stl = os.path.join(output_dir, export_mesh_name).replace("\\", "/")

        segment_step = plan.get_step("segment")
        anatomy = "bone"
        lower_th = 250.0
        upper_th = 2000.0
        if segment_step:
            anatomy = segment_step.parameters.get("target_anatomy", "bone")
            lower_th = float(segment_step.parameters.get("lower_threshold", 250.0))
            upper_th = float(segment_step.parameters.get("upper_threshold", 2000.0))

        code = f'''# ==============================================================================
# SlicerFlow Copilot - Auto-Generated 3D Slicer Execution Script
# Case ID: {plan.case_id} | Plan ID: {plan.plan_id}
# Generated adhering to: AI understands -> Rules validate -> Slicer executes
# ==============================================================================

import os
import sys
import json
import logging
import slicer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("SlicerFlow")

def run_pipeline():
    logger.info("Starting SlicerFlow automated execution pipeline...")
    input_file = "{escaped_input}"
    output_dir = "{escaped_out_dir}"
    os.makedirs(output_dir, exist_ok=True)
    
    results = {{
        "case_id": "{plan.case_id}",
        "steps": [],
        "success": False
    }}

    # 1. LOAD DATA (Volume or 3D Models)
    model_exts = {".vtk", ".stl", ".obj", ".ply", ".vtp", ".vtu", ".g", ".byu", ".off"}
    is_model_dir = os.path.isdir(input_file) and any(os.path.splitext(f)[1].lower() in model_exts for f in os.listdir(input_file))
    is_model_file = not os.path.isdir(input_file) and os.path.splitext(input_file)[1].lower() in model_exts

    volume_node = None
    if is_model_dir:
        for f in sorted(os.listdir(input_file)):
            if os.path.splitext(f)[1].lower() in model_exts:
                slicer.util.loadModel(os.path.join(input_file, f))
        logger.info("Loaded 3D surface models from directory into MRML scene.")
        results["steps"].append({{"operation": "load_models", "status": "SUCCESS"}})
        results["success"] = True
        return results
    elif is_model_file:
        model_node = slicer.util.loadModel(input_file)
        logger.info(f"Loaded 3D surface model node: {{model_node.GetName() if model_node else 'Model'}}")
        results["steps"].append({{"operation": "load_model", "status": "SUCCESS"}})
        results["success"] = True
        return results
    else:
        logger.info(f"Loading volume from {{input_file}}...")
        volume_node = slicer.util.loadVolume(input_file)
        if not volume_node:
            logger.error("Failed to load volume into MRML scene.")
            return results
        logger.info(f"Loaded volume node: {{volume_node.GetName()}} (ID: {{volume_node.GetID()}})")
        results["steps"].append({{"operation": "load_volume", "status": "SUCCESS"}})

    # 2. SEGMENTATION
    logger.info("Initializing segmentation node for {anatomy}...")
    segmentation_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SlicerFlow_Segmentation")
    segmentation_node.CreateDefaultDisplayNodes()
    segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(volume_node)
    
    # Add segment
    segment_id = segmentation_node.GetSegmentation().AddEmptySegment("{anatomy}")
    
    # Create segment editor logic
    segment_editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    segment_editor_widget = slicer.qMRMLSegmentEditorWidget()
    segment_editor_widget.setMRMLScene(slicer.mrmlScene)
    segment_editor_widget.setMRMLSegmentEditorNode(segment_editor_node)
    segment_editor_widget.setSegmentationNode(segmentation_node)
    segment_editor_widget.setSourceVolumeNode(volume_node)
    segment_editor_widget.setCurrentSegmentID(segment_id)
    
    # Apply Threshold effect ({lower_th:.1f} to {upper_th:.1f} HU)
    logger.info("Applying intensity threshold: [{lower_th:.1f}, {upper_th:.1f}] HU...")
    segment_editor_widget.setActiveEffectByName("Threshold")
    effect = segment_editor_widget.activeEffect()
    if effect:
        effect.setParameter("MinimumThreshold", str({lower_th}))
        effect.setParameter("MaximumThreshold", str({upper_th}))
        effect.self().onApply()
    
    results["steps"].append({{"operation": "segment", "status": "SUCCESS"}})

    # 3. 3D MODEL RECONSTRUCTION
    logger.info("Reconstructing closed surface 3D polygonal representation...")
    segmentation_node.CreateClosedSurfaceRepresentation()
    results["steps"].append({{"operation": "generate_model", "status": "SUCCESS"}})

    # 4. EXPORT MESH
    stl_path = "{escaped_stl}"
    logger.info(f"Exporting 3D surface mesh to {{stl_path}}...")
    slicer.modules.segmentations.logic().ExportSegmentsClosedSurfaceRepresentationToFiles(
        output_dir,
        segmentation_node,
        None,  # Export all segments
        "STL"
    )
    results["steps"].append({{"operation": "export", "status": "SUCCESS", "output": stl_path}})
    results["success"] = True
    
    # Save summary manifest
    summary_path = os.path.join(output_dir, "slicer_exec_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info("SlicerFlow pipeline completed successfully!")
    return results

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        logger.error(f"Slicer pipeline execution failed: {{str(e)}}")
        sys.exit(1)
'''
        return code
