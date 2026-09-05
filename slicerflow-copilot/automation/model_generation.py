"""3D Model Generation and Interactive Surface Reconstruction.

Extracts polygonal isosurface meshes via Marching Cubes, exports STL/OBJ files,
and builds interactive WebGL 3D visualizations using Plotly.
"""

import os
import struct
import numpy as np
from typing import Tuple, Dict, Any, Optional
from skimage.measure import marching_cubes
import plotly.graph_objects as go


class Model3DGenerator:
    """Reconstructs 3D surface meshes from volumetric segmentations."""

    @classmethod
    def generate_surface_mesh(
        cls,
        mask: np.ndarray,
        spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        step_size: int = 1
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        """Extract 3D surface mesh using Marching Cubes.
        
        mask has shape (Z, Y, X).
        spacing is (Sx, Sy, Sz).
        Returns:
            vertices: (N, 3) in physical (X, Y, Z) mm coordinates
            faces: (M, 3) triangle indices
            normals: (N, 3) vertex normal vectors
            stats: summary dict
        """
        if np.sum(mask) == 0:
            raise ValueError("Cannot extract 3D surface: segmentation mask is empty.")

        # Marching cubes on (Z, Y, X)
        # spacing for marching cubes should match array axis ordering: (Sz, Sy, Sx)
        spacing_zyx = (spacing[2], spacing[1], spacing[0])
        verts_zyx, faces, normals_zyx, _ = marching_cubes(mask, level=0.5, spacing=spacing_zyx, step_size=step_size)

        # Convert to standard (X, Y, Z) coordinates
        vertices_xyz = np.zeros_like(verts_zyx)
        vertices_xyz[:, 0] = verts_zyx[:, 2]  # X
        vertices_xyz[:, 1] = verts_zyx[:, 1]  # Y
        vertices_xyz[:, 2] = verts_zyx[:, 0]  # Z

        normals_xyz = np.zeros_like(normals_zyx)
        normals_xyz[:, 0] = normals_zyx[:, 2]
        normals_xyz[:, 1] = normals_zyx[:, 1]
        normals_xyz[:, 2] = normals_zyx[:, 0]

        stats = {
            "vertices_count": int(len(vertices_xyz)),
            "faces_count": int(len(faces)),
            "bounds_x": [float(vertices_xyz[:, 0].min()), float(vertices_xyz[:, 0].max())],
            "bounds_y": [float(vertices_xyz[:, 1].min()), float(vertices_xyz[:, 1].max())],
            "bounds_z": [float(vertices_xyz[:, 2].min()), float(vertices_xyz[:, 2].max())],
        }

        return vertices_xyz, faces, normals_xyz, stats

    @classmethod
    def export_stl(cls, vertices: np.ndarray, faces: np.ndarray, output_path: str, binary: bool = True):
        """Export 3D surface mesh as an STL file."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if binary:
            # Write binary STL
            with open(output_path, "wb") as f:
                # 80-byte header
                header = b"SlicerFlow Copilot Auto-Generated 3D Surface Model".ljust(80, b"\0")
                f.write(header)
                # Number of triangles (uint32)
                f.write(struct.pack("<I", len(faces)))
                # Triangles
                for face in faces:
                    v1 = vertices[face[0]]
                    v2 = vertices[face[1]]
                    v3 = vertices[face[2]]
                    # Normal vector (0.0 if not pre-computed)
                    normal = np.cross(v2 - v1, v3 - v1)
                    norm = np.linalg.norm(normal)
                    if norm > 0:
                        normal /= norm
                    else:
                        normal = np.array([0.0, 0.0, 0.0])

                    # 50 bytes per triangle: normal (3f), v1 (3f), v2 (3f), v3 (3f), attr byte count (H)
                    data = struct.pack(
                        "<12fH",
                        normal[0], normal[1], normal[2],
                        v1[0], v1[1], v1[2],
                        v2[0], v2[1], v2[2],
                        v3[0], v3[1], v3[2],
                        0
                    )
                    f.write(data)
        else:
            # Write ASCII STL
            with open(output_path, "w") as f:
                f.write("solid SlicerFlowModel\n")
                for face in faces:
                    v1 = vertices[face[0]]
                    v2 = vertices[face[1]]
                    v3 = vertices[face[2]]
                    normal = np.cross(v2 - v1, v3 - v1)
                    norm = np.linalg.norm(normal)
                    if norm > 0:
                        normal /= norm
                    f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
                    f.write("    outer loop\n")
                    f.write(f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n")
                    f.write(f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n")
                    f.write(f"      vertex {v3[0]:.6e} {v3[1]:.6e} {v3[2]:.6e}\n")
                    f.write("    endloop\n")
                    f.write("  endfacet\n")
                f.write("endsolid SlicerFlowModel\n")

    @classmethod
    def export_obj(cls, vertices: np.ndarray, faces: np.ndarray, output_path: str):
        """Export 3D surface mesh as an OBJ file."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write("# SlicerFlow Copilot 3D OBJ Export\n")
            for v in vertices:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            for face in faces:
                # 1-indexed in OBJ
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

    @classmethod
    def create_plotly_figure(
        cls,
        vertices: np.ndarray,
        faces: np.ndarray,
        color: str = "#E8D8C8",
        title: str = "3D Anatomical Reconstruction"
    ) -> go.Figure:
        """Build an interactive 3D WebGL Mesh figure."""
        mesh = go.Mesh3d(
            x=vertices[:, 0],
            y=vertices[:, 1],
            z=vertices[:, 2],
            i=faces[:, 0],
            j=faces[:, 1],
            k=faces[:, 2],
            color=color,
            opacity=1.0,
            lighting=dict(
                ambient=0.4,
                diffuse=0.8,
                specular=0.5,
                roughness=0.5,
                fresnel=0.2
            ),
            lightposition=dict(x=100, y=200, z=400),
            name="Anatomy"
        )

        fig = go.Figure(data=[mesh])
        fig.update_layout(
            title=dict(text=title, font=dict(size=14, color="#E2E8F0")),
            scene=dict(
                xaxis=dict(title="X (mm)", backgroundcolor="#0F172A", gridcolor="#334155", showbackground=True),
                yaxis=dict(title="Y (mm)", backgroundcolor="#0F172A", gridcolor="#334155", showbackground=True),
                zaxis=dict(title="Z (mm)", backgroundcolor="#0F172A", gridcolor="#334155", showbackground=True),
                aspectmode="data"
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            paper_bgcolor="#0A0E17",
        )
        return fig
