# Severn Trent Water

This integration links to your Severn Trent Water account and retrieves all available daily water meter usage data. It stores it in a statistic that can be added to your Energy dashboard.

## Pre-requisites

Severn Trent Water do not supply an API to access your data so this integration scrapes the data using Selenium. You will need to supply your own instance and provide the URL when setting up the integration. A simple solution is to use a docker container with the selenium/standalone-chrome image:

```bash
docker run -d -p 4444:4444 --name selenium-chrome --env SE_VNC_NO_PASSWORD=true --env SE_VNC_VIEW_ONLY=false selenium/standalone-chrome
```

Home Assistant needs to be able to access this container.

## Installation

1. Open the folder for your Home Assistant configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` folder there, you need to create it.
1. Download the `custom_components/st_water` folder in this repository into the `custom_components` folder from the previous step.
1. Restart Home Assistant.
1. In the Home Assistant UI go to "Settings" -> "Devices & Services" click "+ Add Integration" and search for "Severn Trent Water".
1. Enter the username and password you use to login to your account and update the URL to point to your Selenium instance.

## Statistics

This integration creates a statistic called `st_water:consumption`. You can find this by going to `Developer Tools` then `Statistics`. You can add this to your custom Dashboard using a Statistics Graph card or it can be used in your Energy dashboard for Water Consumption.

## Configuration

No configuration can be done in the UI. In the file `const.py`:

| Option | Description |
|-|-|
|SCAN_INTERVAL|The time in seconds between data refreshes. STW say they update once a day at midnight but they are not consistent so you may want to change this to twice a day.|
|DEBUG_MODE|Set this to True to show some logging in the home-assistant.log. It will also turn headless mode off for Selenium so you can watch what it is doing in your Selenium session browser.|

## Limitations and Future

A few limitations which may see future development work:

- STW are changing their portal and will eventually have a new login and other screens. If you are already on that then this integration may not work. I will update this when I am switched to the new portal.
- STW only show the last 8 days of hourly data. It does summarise per day for about 8 weeks and per month for, possibly, all years. However, this integration only concerns itself with the hourly data for now.
- The hourly data has no costs shown with it so that data is not captured here.
