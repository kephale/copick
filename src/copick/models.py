import json
from typing import Dict, List, Literal, MutableMapping, Optional, Tuple, TypeVar, Union

import numpy as np

# Should work with pydantic 1 and 2
import pydantic

if pydantic.VERSION.startswith("1"):
    from pydantic import BaseModel, validator
elif pydantic.VERSION.startswith("2"):
    from pydantic.v1 import BaseModel, validator
else:
    raise ImportError(f"Unsupported pydantic version {pydantic.VERSION}.")

from trimesh.parent import Geometry

TPickableObject = TypeVar("TPickableObject", bound="PickableObject")
TCopickConfig = TypeVar("TCopickConfig", bound="CopickConfig")
TCopickLocation = TypeVar("TCopickLocation", bound="CopickLocation")
TCopickPoint = TypeVar("TCopickPoint", bound="CopickPoint")
TCopickPicks = TypeVar("TCopickPicks", bound="CopickPicks")
TCopickMesh = TypeVar("TCopickMesh", bound="CopickMesh")
TCopickSegmentation = TypeVar("TCopickSegmentation", bound="CopickSegmentation")
TCopickTomogram = TypeVar("TCopickTomogram", bound="CopickTomogram")
TCopickFeatures = TypeVar("TCopickFeatures", bound="CopickFeatures")
TCopickVoxelSpacing = TypeVar("TCopickVoxelSpacing", bound="CopickVoxelSpacing")
TCopickRun = TypeVar("TCopickRun", bound="CopickRun")
TCopickRoot = TypeVar("TCopickRoot", bound="CopickRoot")


class PickableObject(BaseModel):
    name: str
    is_particle: bool
    label: Optional[int]
    color: Optional[Tuple[int, int, int, int]]
    emdb_id: Optional[str] = None
    pdb_id: Optional[str] = None

    @validator("label")
    def validate_label(cls, v) -> int:
        """Validate the label."""
        assert v != 0, "Label 0 is reserved for background."
        return v

    @validator("color")
    def validate_color(cls, v) -> Tuple[int, int, int, int]:
        """Validate the color."""
        assert len(v) == 4, "Color must be a 4-tuple (RGBA)."
        assert all(0 <= c <= 255 for c in v), "Color values must be in the range [0, 255]."
        return v


class CopickConfig(BaseModel):
    name: Optional[str] = "CoPick"
    """Name of the CoPick project."""
    description: Optional[str] = "Let's CoPick!"
    """Description of the CoPick project."""
    version: Optional[str] = "0.1.0"
    """Version of the CoPick API."""

    # List[PickableObject]
    pickable_objects: List[TPickableObject]
    """Index for available pickable objects."""

    user_id: Optional[str] = None
    """Unique identifier for the user (e.g. when distributing the config file to users)."""

    voxel_spacings: Optional[List[float]] = None
    """Index for available voxel spacings."""

    runs: Optional[List[str]] = None
    """Index for run names."""

    # Dict[voxel_spacing: List of tomogram types]
    tomograms: Optional[Dict[float, List[str]]] = {}
    """Index for available voxel spacings and tomogram types."""

    # Dict[voxel_spacing: List of tomogram types]
    features: Optional[Dict[float, List[str]]] = {}
    """Index for available features. Must be computed on the tomogram types."""

    # List[feature type]
    feature_types: Optional[List[str]] = []
    """Index for available feature types."""

    # Dict[object_name: List[pre-pick tool names]]
    available_pre_picks: Optional[Dict[str, List[str]]] = {}
    """Index for available pre-pick tools."""

    # List[seg tool names]
    available_pre_segmentations: Optional[List[str]] = []
    """Index for available pre-segmentations."""

    # Dict[object_name: List[pre-pick tool names]]
    available_pre_meshes: Optional[Dict[str, List[str]]] = []
    """Index for available pre-meshes."""

    @classmethod
    def from_file(cls, filename: str) -> TCopickConfig:
        with open(filename) as f:
            return cls(**json.load(f))


class CopickLocation(BaseModel):
    x: float
    y: float
    z: float


class CopickPoint(BaseModel):
    location: TCopickLocation
    transformation_: Optional[List[List[float]]] = (
        [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
    )
    instance_id: Optional[int] = 0
    score: Optional[float] = 1.0

    class Config:
        arbitrary_types_allowed = True

    @validator("transformation_")
    def validate_transformation(cls, v) -> List[List[float]]:
        """Validate the transformation matrix."""
        arr = np.array(v)
        assert arr.shape == (4, 4), "transformation must be a 4x4 matrix."
        assert arr[3, 3] == 1.0, "Last element of transformation matrix must be 1.0."
        assert np.allclose(arr[3, :], [0.0, 0.0, 0.0, 1.0]), "Last row of transformation matrix must be [0, 0, 0, 1]."
        return v

    @property
    def transformation(self) -> np.ndarray:
        return np.array(self.transformation_)

    @transformation.setter
    def transformation(self, value: np.ndarray) -> None:
        assert value.shape == (4, 4), "Transformation must be a 4x4 matrix."
        assert value[3, 3] == 1.0, "Last element of transformation matrix must be 1.0."
        assert np.allclose(value[3, :], [0.0, 0.0, 0.0, 1.0]), "Last row of transformation matrix must be [0, 0, 0, 1]."
        self.transformation_ = value.tolist()


class CopickRoot:
    def __init__(self, config: TCopickConfig):
        self.config = config
        """Reference to the configuration for this root. This will only be populated at runtime."""

        self._runs: Optional[List[TCopickRun]] = None
        """References to the runs for this project. Either populated from config or lazily loaded when CopickRoot.runs
        is accessed."""

        # If runs are specified in the config, create them
        if config.runs is not None:
            self._runs = {run_name: CopickRun(self, CopickRunMeta(name=run_name)) for run_name in config.runs}

    @property
    def user_id(self) -> str:
        """Unique identifier for the user."""
        return self.config.user_id

    @user_id.setter
    def user_id(self, value: str) -> None:
        self.config.user_id = value

    @property
    def session_id(self) -> str:
        """Unique identifier for the session."""
        return self.config.user_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self.config.user_id = value

    def query(self) -> List[TCopickRun]:
        """Override this method to query for runs."""
        pass

    @property
    def runs(self) -> List[TCopickRun]:
        """Lazy load runs via a RESTful interface or filesystem"""
        if self._runs is None:
            self._runs = self.query()

        return self._runs

    def refresh(self) -> None:
        """Refresh the self-referential tree structure."""
        self._runs = self.query()


class CopickRunMeta(BaseModel):
    name: str
    """Name of the run."""


class CopickRun:
    def __init__(self, root: TCopickRoot, meta: CopickRunMeta, config: Optional[TCopickConfig] = None):
        self.meta = meta
        """Metadata for this run."""
        self.root = root
        """Reference to the root this run belongs to. This will only be populated at runtime and is excluded from
        serialization."""

        self._voxel_spacings: Optional[Dict[float, TCopickVoxelSpacing]] = None
        """Voxel spacings for this run. Either populated from config or lazily loaded when CopickRun.voxel_spacings is
        accessed."""

        self._picks: Optional[List[TCopickPicks]] = None
        """Picks for this run. Either populated from config or lazily loaded when CopickRun.picks is
        accessed."""

        self._meshes: Optional[List[TCopickMesh]] = None
        """Meshes for this run. Either populated from config or lazily loaded when CopickRun.picks is
        accessed."""

        self._segmentations: Optional[List[TCopickSegmentation]] = None
        """Segmentations for this run. Either populated from config or lazily loaded when
        CopickRun.segmentations is accessed."""

        if config is not None:
            voxel_spacings_metas = [
                CopickVoxelSpacingMeta(run=self, voxel_size=vs, config=config) for vs in config.tomograms
            ]
            self._voxel_spacings = [CopickVoxelSpacing(run=self, meta=vs) for vs in voxel_spacings_metas]

            #####################
            # Picks from config #
            #####################
            # Select all available pre-picks for this run
            avail = config.available_pre_picks.keys()
            avail = [a for a in avail if a[0] == self.name]

            # Pre-defined picks
            for av in avail:
                object_name = av[1]
                prepicks = config.available_pre_picks[av]

                for pp in prepicks:
                    pm = CopickPicksFile(
                        pickable_object_name=object_name,
                        user_id=pp,
                        session_id="0",
                        run_name=self.name,
                    )
                    self._picks.append(CopickPicks(run=self, file=pm))

            ######################
            # Meshes from config #
            ######################
            for object_name, tool_names in config.available_pre_meshes.items():
                for mesh_tool in tool_names:
                    mm = CopickMeshMeta(pickable_object_name=object_name, user_id=mesh_tool, session_id="0")
                    com = CopickMesh(run=self, meta=mm)
                    self._meshes.append(com)

            #############################
            # Segmentations from config #
            #############################
            for seg_tool in config.available_pre_segmentations:
                sm = CopickSegmentationMeta(run=self, user_id=seg_tool, session_id="0")
                cos = CopickSegmentation(run=self, meta=sm)
                self._segmentations.append(cos)

    @property
    def name(self):
        return self.meta.name

    @name.setter
    def name(self, value: str) -> None:
        self.meta.name = value

    def query_voxelspacings(self) -> List[TCopickVoxelSpacing]:
        """Override this method to query for voxel_spacings."""
        pass

    def query_picks(self) -> List[TCopickPicks]:
        """Override this method to query for picks."""
        pass

    def query_meshes(self) -> List[TCopickMesh]:
        """Override this method to query for meshes."""
        pass

    def query_segmentations(self) -> List[TCopickSegmentation]:
        """Override this method to query for segmentations."""
        pass

    @property
    def voxel_spacings(self) -> List[TCopickVoxelSpacing]:
        """Lazy load voxel spacings via a RESTful interface or filesystem."""
        if self._voxel_spacings is None:
            self._voxel_spacings = self.query_voxelspacings()

        return self._voxel_spacings

    @property
    def picks(self) -> List[TCopickPicks]:
        """Lazy load picks via a RESTful interface or filesystem."""
        if self._picks is None:
            self._picks = self.query_picks()

        return self._picks

    @property
    def meshes(self) -> List[TCopickMesh]:
        """Lazy load meshes via a RESTful interface or filesystem."""
        if self._meshes is None:
            self._meshes = self.query_meshes()

        return self._meshes

    @property
    def segmentations(self) -> List[TCopickSegmentation]:
        """Lazy load segmentations via a RESTful interface or filesystem."""
        if self._segmentations is None:
            self._segmentations = self.query_segmentations()

        return self._segmentations

    def new_voxel_spacing(self, voxel_size: float) -> TCopickVoxelSpacing:
        """Create a new voxel spacing object."""
        vm = CopickVoxelSpacingMeta(voxel_size=voxel_size)
        return CopickVoxelSpacing(run=self, meta=vm)

    def new_picks(self, object_name: str, session_id: str, user_id: Optional[str] = None) -> TCopickPicks:
        """Create a new picks object."""
        if object_name not in [o.name for o in self.root.config.pickable_objects]:
            raise ValueError(f"Object name {object_name} not found in pickable objects.")

        uid = self.root.config.user_id

        if user_id is not None:
            uid = user_id

        if uid is None:
            raise ValueError("User ID must be set in the root config or supplied to new_picks.")

        pm = CopickPicksFile(
            pickable_object_name=object_name,
            user_id=uid,
            session_id=session_id,
            run_name=self.name,
        )
        return CopickPicks(run=self, file=pm)

    def new_mesh(self, object_name: str, session_id: str, user_id: Optional[str] = None) -> TCopickMesh:
        """Create a new mesh object."""
        if object_name not in [o.name for o in self.root.config.pickable_objects]:
            raise ValueError(f"Object name {object_name} not found in pickable objects.")

        uid = self.root.config.user_id

        if user_id is not None:
            uid = user_id

        if uid is None:
            raise ValueError("User ID must be set in the root config or supplied to new_mesh.")

        mm = CopickMeshMeta(
            pickable_object_name=object_name,
            user_id=uid,
            session_id=session_id,
        )
        return CopickMesh(run=self, meta=mm)

    def new_segmentation(self, session_id: str, user_id: Optional[str] = None) -> TCopickSegmentation:
        """Create a new segmentation object."""

        uid = self.root.config.user_id

        if user_id is not None:
            uid = user_id

        if uid is None:
            raise ValueError("User ID must be set in the root config or supplied to new_segmentation.")

        sm = CopickSegmentationMeta(
            user_id=self.root.config.user_id,
            session_id=session_id,
        )
        return CopickSegmentation(run=self, meta=sm)

    def refresh_voxel_spacings(self) -> None:
        """Refresh the voxel spacings."""
        self._voxel_spacings = self.query_voxelspacings()

    def refresh_picks(self) -> None:
        """Refresh the picks."""
        self._picks = self.query_picks()

    def refresh_meshes(self) -> None:
        """Refresh the meshes."""
        self._meshes = self.query_meshes()

    def refresh_segmentations(self) -> None:
        """Refresh the segmentations."""
        self._segmentations = self.query_segmentations()

    def refresh(self) -> None:
        """Refresh the children."""
        self.refresh_voxel_spacings()
        self.refresh_picks()
        self.refresh_meshes()
        self.refresh_segmentations()


class CopickVoxelSpacingMeta(BaseModel):
    voxel_size: float


class CopickVoxelSpacing:
    def __init__(self, run: TCopickRun, meta: CopickVoxelSpacingMeta, config: Optional[TCopickConfig] = None):
        self.run = run
        self.meta = meta

        self._tomograms: Optional[List[TCopickTomogram]] = None
        """References to the tomograms for this voxel spacing."""

        if config is not None:
            tomo_metas = [CopickTomogramMeta(tomo_type=tt) for tt in config.tomograms[self.voxel_size]]
            self._tomograms = {
                tm.tomo_type: CopickTomogram(voxel_spacing=self, meta=tm, config=config) for tm in tomo_metas
            }

    @property
    def voxel_size(self) -> float:
        return self.meta.voxel_size

    def query_tomograms(self) -> List[TCopickTomogram]:
        """Override this method to query for tomograms."""
        pass

    @property
    def tomograms(self) -> List[TCopickTomogram]:
        """Lazy load tomograms via a RESTful interface or filesystem."""
        if self._tomograms is None:
            self._tomograms = self.query_tomograms()

        return self._tomograms

    def refresh_tomograms(self) -> None:
        """Refresh the tomograms."""
        self._tomograms = self.query_tomograms()

    def refresh(self) -> None:
        """Refresh the children."""
        self.refresh_tomograms()

    def new_tomogram(self, tomo_type: str) -> TCopickTomogram:
        """Create a new tomogram object."""
        if tomo_type in [tomo.tomo_type for tomo in self.tomograms]:
            raise ValueError(f"Tomogram type {tomo_type} already exists for this voxel spacing.")

        tm = CopickTomogramMeta(tomo_type=tomo_type)
        return CopickTomogram(voxel_spacing=self, meta=tm)


class CopickTomogramMeta(BaseModel):
    tomo_type: str
    """Type of the tomogram."""


class CopickTomogram:
    def __init__(
        self,
        voxel_spacing: TCopickVoxelSpacing,
        meta: CopickTomogramMeta,
        config: Optional[TCopickConfig] = None,
    ):
        self.meta = meta
        """Metadata for this tomogram."""
        self.voxel_spacing = voxel_spacing
        """Voxel spacing this tomogram belongs to."""

        self._features: Optional[List[TCopickFeatures]] = None
        """Features for this tomogram."""

        if config is not None and self.tomo_type in config.features[self.voxel_spacing.voxel_size]:
            feat_metas = [CopickFeaturesMeta(tomo_type=self.tomo_type, feature_type=ft) for ft in config.feature_types]
            self._features = {fm.feature_type: CopickFeatures(tomogram=self, meta=fm) for fm in feat_metas}

    @property
    def tomo_type(self) -> str:
        return self.meta.tomo_type

    @property
    def features(self) -> List[TCopickFeatures]:
        """Lazy load features via a RESTful interface or filesystem."""
        if self._features is None:
            self._features = self.query_features()

        return self._features

    @features.setter
    def features(self, value: List[TCopickFeatures]) -> None:
        """Set the features."""
        self._features = value

    def new_features(self, feature_type: str) -> TCopickFeatures:
        """Create a new features object."""
        if feature_type in [f.feature_type for f in self.features]:
            raise ValueError(f"Feature type {feature_type} already exists for this tomogram.")

        fm = CopickFeaturesMeta(tomo_type=self.tomo_type, feature_type=feature_type)
        return CopickFeatures(tomogram=self, meta=fm)

    def query_features(self) -> List[TCopickFeatures]:
        """Override this method to query for features."""
        pass

    def refresh_features(self) -> None:
        """Refresh the features."""
        self._features = self.query_features()

    def refresh(self) -> None:
        """Refresh the children."""
        self.refresh_features()

    def zarr(self) -> MutableMapping:
        """Override to return the Zarr store for this tomogram. Also needs to handle creating the store if it
        doesn't exist."""
        pass


class CopickFeaturesMeta(BaseModel):
    tomo_type: str
    """Type of the tomogram that the features were computed on."""
    feature_type: str
    """Type of the features contained."""


class CopickFeatures:
    def __init__(self, tomogram: TCopickTomogram, meta: CopickFeaturesMeta):
        self.meta: CopickFeaturesMeta = meta
        """Metadata for this tomogram."""
        self.tomogram: TCopickTomogram = tomogram
        """Tomogram these features belong to."""

    @property
    def tomo_type(self) -> str:
        return self.meta.tomo_type

    @property
    def feature_type(self) -> str:
        return self.meta.feature_type

    def zarr(self) -> MutableMapping:
        """Override to return the Zarr store for this feature set. Also needs to handle creating the store if it
        doesn't exist."""
        pass


class CopickPicksFile(BaseModel):
    pickable_object_name: str
    """Pickable object name from CopickConfig.pickable_objects[X].name"""

    user_id: str
    """Unique identifier for the user or tool name."""

    session_id: Union[str, Literal["0"]]
    """Unique identifier for the pick session (prevent race if they run multiple instances of napari, ChimeraX, etc)
       If it is 0, this pick was generated by a tool."""

    run_name: Optional[str]
    """Name of the run this pick belongs to."""
    voxel_spacing: Optional[float]
    """Voxel spacing for the tomogram this pick belongs to."""
    unit: str = "angstrom"
    """Unit for the location of the pick."""

    points: Optional[List[TCopickPoint]] = None
    """References to the points for this pick."""


class CopickPicks:
    def __init__(self, run: TCopickRun, file: CopickPicksFile):
        self.meta: CopickPicksFile = file
        """Metadata for this pick."""
        self.run: TCopickRun = run
        """Run this pick belongs to."""

    def _load(self) -> CopickPicksFile:
        """Override this method to load points from a RESTful interface or filesystem."""
        pass

    def _store(self):
        """Override this method to store points with a RESTful interface or filesystem. Also needs to handle creating
        the file if it doesn't exist."""
        pass

    def load(self) -> CopickPicksFile:
        """Load the points."""
        self.meta = self._load()

        return self.meta

    def store(self):
        """Store the points."""
        self._store()

    @property
    def pickable_object_name(self) -> str:
        """Pickable object name from CopickConfig.pickable_objects[X].name"""
        return self.meta.pickable_object_name

    @property
    def user_id(self) -> str:
        """Unique identifier for the user or tool name."""
        return self.meta.user_id

    @property
    def session_id(self) -> Union[str, Literal["0"]]:
        """Unique identifier for the pick session."""
        return self.meta.session_id

    @property
    def points(self) -> List[TCopickPoint]:
        """Lazy load points via a RESTful interface or filesystem."""
        if self.meta.points is None:
            self.meta = self.load()

        return self.meta.points

    @points.setter
    def points(self, value: List[TCopickPoint]) -> None:
        """Set the points."""
        self.meta.points = value

    def refresh(self) -> None:
        """Refresh the children."""
        self.meta = self.load()


class CopickMeshMeta(BaseModel):
    pickable_object_name: str
    """Pickable object name from CopickConfig.pickable_objects[X].name"""

    user_id: str
    """Unique identifier for the user or tool name."""

    session_id: Union[str, Literal["0"]]
    """Unique identifier for the pick session (prevent race if they run multiple instances of napari, ChimeraX, etc)
       If it is 0, this pick was generated by a tool."""


class CopickMesh:
    def __init__(self, run: TCopickRun, meta: CopickMeshMeta):
        self.meta: CopickMeshMeta = meta
        """Metadata for this pick."""
        self.run: TCopickRun = run
        """Run this pick belongs to."""

        self._mesh = None

    @property
    def pickable_object_name(self) -> str:
        """Pickable object name from CopickConfig.pickable_objects[X].name"""
        return self.meta.pickable_object_name

    @property
    def user_id(self) -> str:
        """Unique identifier for the user or tool name."""
        return self.meta.user_id

    @property
    def session_id(self) -> Union[str, Literal["0"]]:
        """Unique identifier for the pick session."""
        return self.meta.session_id

    def _load(self) -> Geometry:
        """Override this method to load mesh from a RESTful interface or filesystem."""
        pass

    def _store(self):
        """Override this method to store mesh with a RESTful interface or filesystem. Also needs to handle creating
        the file if it doesn't exist."""
        pass

    def load(self) -> Geometry:
        """Load the mesh."""
        self._mesh = self._load()

        return self._mesh

    def store(self):
        """Store the mesh."""
        self._store()

    @property
    def mesh(self) -> Geometry:
        """Lazy load mesh via a RESTful interface or filesystem."""
        if self._mesh is None:
            self._mesh = self.load()

        return self._mesh

    @mesh.setter
    def mesh(self, value: Geometry) -> None:
        """Set the mesh."""
        self._mesh = value

    @property
    def from_tool(self) -> bool:
        return self.session_id == "0"

    def refresh(self) -> None:
        """Refresh the children."""
        self._mesh = self.load()


class CopickSegmentationMeta(BaseModel):
    user_id: str
    """Unique identifier for the user or tool name."""

    session_id: Union[str, Literal["0"]]
    """Unique identifier for the pick"""


class CopickSegmentation:
    def __init__(self, run: TCopickRun, meta: CopickSegmentationMeta):
        self.meta: CopickSegmentationMeta = meta
        """Metadata for this pick."""
        self.run: TCopickRun = run
        """Run this pick belongs to."""

    @property
    def user_id(self) -> str:
        """Unique identifier for the user or tool name."""
        return self.meta.user_id

    @property
    def session_id(self) -> Union[str, Literal["0"]]:
        """Unique identifier for the pick session."""
        return self.meta.session_id

    @property
    def from_tool(self) -> bool:
        return self.session_id == "0"

    def zarr(self) -> MutableMapping:
        """Override to return the Zarr store for this segmentation. Also needs to handle creating the store if it
        doesn't exist."""
        pass
