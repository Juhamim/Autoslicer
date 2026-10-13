"""JSON schemas for action validation."""

from typing import Literal, Optional, List, Union
from pydantic import BaseModel, Field, field_validator


class ActionBase(BaseModel):
    type: str


class ShowAction(ActionBase):
    type: Literal["SHOW"]
    target: str


class HideAction(ActionBase):
    type: Literal["HIDE"]
    target: str


class ShowOnlyAction(ActionBase):
    type: Literal["SHOW_ONLY"]
    targets: List[str]


class SetOpacityAction(ActionBase):
    type: Literal["SET_OPACITY"]
    target: str
    value: float = Field(ge=0.0, le=1.0)


class SetColorAction(ActionBase):
    type: Literal["SET_COLOR"]
    target: str
    color: List[float] = Field(min_length=3, max_length=3)


class ResetDisplayAction(ActionBase):
    type: Literal["RESET_DISPLAY"]
    target: str


class ResetViewAction(ActionBase):
    type: Literal["RESET_VIEW"]


class ZoomToAction(ActionBase):
    type: Literal["ZOOM_TO"]
    target: str


class ViewAction(ActionBase):
    type: Literal["THREE_D_VIEW", "AXIAL_VIEW", "SAGITTAL_VIEW", "CORONAL_VIEW"]


class ListObjectsAction(ActionBase):
    type: Literal["LIST_OBJECTS"]


class ListVisibleObjectsAction(ActionBase):
    type: Literal["LIST_VISIBLE_OBJECTS"]


class OpenFolderAction(ActionBase):
    type: Literal["OPEN_FOLDER"]
    path: str


class ImportDicomAction(ActionBase):
    type: Literal["IMPORT_DICOM"]
    path: str


class LoadVolumeAction(ActionBase):
    type: Literal["LOAD_VOLUME"]
    path: str


class LoadModelAction(ActionBase):
    type: Literal["LOAD_MODEL"]
    path: str


class LoadSegmentationAction(ActionBase):
    type: Literal["LOAD_SEGMENTATION"]
    path: str


Action = Union[
    ShowAction,
    HideAction,
    ShowOnlyAction,
    SetOpacityAction,
    SetColorAction,
    ResetDisplayAction,
    ResetViewAction,
    ZoomToAction,
    ViewAction,
    ListObjectsAction,
    ListVisibleObjectsAction,
    OpenFolderAction,
    ImportDicomAction,
    LoadVolumeAction,
    LoadModelAction,
    LoadSegmentationAction,
]


class ActionPlan(BaseModel):
    version: str = "1.0"
    reply: str
    actions: List[Action] = []


class SceneObject(BaseModel):
    name: str
    type: str
    visible: bool = True
    opacity: Optional[float] = None
    color: Optional[List[float]] = None


class SceneSummary(BaseModel):
    volumes: List[SceneObject] = []
    models: List[SceneObject] = []
    segmentations: List[SceneObject] = []
    markups: List[SceneObject] = []
    transforms: List[SceneObject] = []


ALLOWED_ACTIONS = {
    "SHOW",
    "HIDE",
    "SHOW_ONLY",
    "SET_OPACITY",
    "SET_COLOR",
    "RESET_DISPLAY",
    "RESET_VIEW",
    "ZOOM_TO",
    "THREE_D_VIEW",
    "AXIAL_VIEW",
    "SAGITTAL_VIEW",
    "CORONAL_VIEW",
    "LIST_OBJECTS",
    "LIST_VISIBLE_OBJECTS",
    "OPEN_FOLDER",
    "IMPORT_DICOM",
    "LOAD_VOLUME",
    "LOAD_MODEL",
    "LOAD_SEGMENTATION",
}

ACTION_CLASSES = {
    "SHOW": ShowAction,
    "HIDE": HideAction,
    "SHOW_ONLY": ShowOnlyAction,
    "SET_OPACITY": SetOpacityAction,
    "SET_COLOR": SetColorAction,
    "RESET_DISPLAY": ResetDisplayAction,
    "RESET_VIEW": ResetViewAction,
    "ZOOM_TO": ZoomToAction,
    "THREE_D_VIEW": ViewAction,
    "AXIAL_VIEW": ViewAction,
    "SAGITTAL_VIEW": ViewAction,
    "CORONAL_VIEW": ViewAction,
    "LIST_OBJECTS": ListObjectsAction,
    "LIST_VISIBLE_OBJECTS": ListVisibleObjectsAction,
    "OPEN_FOLDER": OpenFolderAction,
    "IMPORT_DICOM": ImportDicomAction,
    "LOAD_VOLUME": LoadVolumeAction,
    "LOAD_MODEL": LoadModelAction,
    "LOAD_SEGMENTATION": LoadSegmentationAction,
}