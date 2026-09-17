from django.contrib import admin

from . import models


admin.site.register([
    models.Team, models.Stadium, models.HomeContext, models.PostseasonStage,
    models.Game, models.StandingHistory, models.SeatZone, models.TicketPrice,
    models.TicketPolicy, models.SeatMap, models.SeatMapAsset, models.SeatScope,
    models.SeatView, models.Transport, models.FoodStore,
    models.FoodStoreLocation, models.FoodStoreMenu, models.StadiumContent,
    models.Facility,
])
