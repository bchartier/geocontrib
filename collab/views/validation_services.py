from collab import models
from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings

import logging


def validate_geom(geom, feature, project):
    """
        Validate the geom field
        @return geom / error message
    """
    # get geom
    geom_type = project.get_geom(feature)
    try:
        geom_obj = GEOSGeometry(geom, srid=settings.DB_SRID)
    except Exception as e:
        msg = "Le format de votre géométrie est incorrect. Veuillez le corriger"
        logger = logging.getLogger(__name__)
        logger.exception(msg)
        return '',  msg
    # test if the geom type is correct
    if not geom_obj.geom_type.upper() in geom_type.upper():
        msg = "Le type de géométrie saisie n'est pas celle définie pour ce type de signalement. Veuillez le corriger"
        logger = logging.getLogger(__name__)
        logger.exception(msg)
        return '',  msg
    return geom_obj, ''
