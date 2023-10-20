import json
import threading

import PySimpleGUI as sg
import requests


class Container:
    def __init__(self):
        self.services = {}
        self.instances = {}

    def register(self, name, service, *args):
        self.services[name] = (service, args)

    def get(self, name):
        if name not in self.instances:
            service, args = self.services[name]
            self.instances[name] = service(*args)
        return self.instances[name]


class Observable:
    def __init__(self, initial_value):
        self.data = initial_value
        self.callbacks = []

    def set(self, value):
        self.data = value
        for callback in self.callbacks:
            callback(value)

    def get(self):
        return self.data

    def bind(self, callback):
        self.callbacks.append(callback)


class WeatherModel:
    def __init__(self, api_key):
        self.api_key = api_key

    def fetch_data(self, endpoint, location_key):
        url = endpoint.format(location_key, self.api_key)
        r = requests.get(url)
        return json.loads(r.text)


class WeatherViewModel:
    def __init__(self, model):
        self.model = model
        self.place_to_key = {}
        self.place = Observable('')
        self.weather = Observable('')
        self.forecast = Observable('')
        self.uv = Observable('')
        self.hourly = Observable('')
        self.historical = Observable('')

    def update_places(self):
        if not self.place.get().strip():
            return []
        self.place_to_key = {}
        places = self.model.fetch_data(
            'http://dataservice.accuweather.com/locations/v1/cities/autocomplete?apikey={1}&q={0}', self.place.get())
        if not places:
            return []
        for place in places:
            place_str = f"{place['LocalizedName']}, {place['Country']['LocalizedName']}, {place['AdministrativeArea']['LocalizedName']}"
            self.place_to_key[place_str] = place['Key']
        return list(self.place_to_key.keys())

    def update_all(self, selected):
        location_key = self.place_to_key[selected]
        weather_data = self.model.fetch_data('http://dataservice.accuweather.com/currentconditions/v1/{0}?apikey={1}',
                                             location_key)
        weather_text = f"Weather: {weather_data[0]['WeatherText']}\nTemperature: {weather_data[0]['Temperature']['Metric']['Value']}°C"
        self.weather.set(weather_text)

        forecast_data = self.model.fetch_data(
            'http://dataservice.accuweather.com/forecasts/v1/daily/5day/{0}?apikey={1}&metric=true', location_key)
        forecast_text = "5-day Forecast:\n"
        for day in forecast_data['DailyForecasts']:
            forecast_text += f"{day['Date'][:10]}: {day['Temperature']['Minimum']['Value']}°C - {day['Temperature']['Maximum']['Value']}°C\n"
        self.forecast.set(forecast_text)

        uv_data = self.model.fetch_data('http://dataservice.accuweather.com/indices/v1/daily/1day/{0}/-15?apikey={1}',
                                        location_key)
        self.uv.set(f"UV Index: {uv_data[0]['Category']}")

        forecast_12hr_data = self.model.fetch_data(
            'http://dataservice.accuweather.com/forecasts/v1/hourly/12hour/{0}?apikey={1}&metric=true', location_key)
        forecast_12hr_text = "12-hour Forecast:\n"
        for hour in forecast_12hr_data:
            forecast_12hr_text += f"{hour['DateTime'][-14:-9]}: {hour['Temperature']['Value']}°C\n"
        self.hourly.set(forecast_12hr_text)

        historical_data = self.model.fetch_data(
            'http://dataservice.accuweather.com/currentconditions/v1/{0}/historical?apikey={1}', location_key)
        historical_text = "Historical Data:\n"
        for record in historical_data:
            historical_text += f"{record['LocalObservationDateTime'][:16]}: {record['Temperature']['Metric']['Value']}°C\n"
        self.historical.set(historical_text)


def main():
    vm = container.get('WeatherViewModel')
    sg.theme('LightGreen')
    layout = [
        [sg.Text('Place:'), sg.Input(enable_events=True, key='-PLACE-')],
        [sg.Listbox([], size=(50, 5), enable_events=True, key='-PLACES-', visible=False)],
        [sg.Text('', size=(50, 2), key='-WEATHER-')],
        [sg.Text('', size=(50, 6), key='-FORECAST-')],
        [sg.Text('', size=(50, 1), key='-UV-')],
        [sg.Text('', size=(50, 13), key='-HOUR-')],
        [sg.Text('', size=(50, 8), key='-HISTORICAL-')],
        [sg.Button('Clear'), sg.Button('Exit')]
    ]
    window = sg.Window('Weather App', layout)
    debounce_timer = None
    debounce_time = 0.3

    vm.weather.bind(lambda value: window['-WEATHER-'].update(value))
    vm.forecast.bind(lambda value: window['-FORECAST-'].update(value))
    vm.uv.bind(lambda value: window['-UV-'].update(value))
    vm.hourly.bind(lambda value: window['-HOUR-'].update(value))
    vm.historical.bind(lambda value: window['-HISTORICAL-'].update(value))

    while True:
        event, values = window.read()
        if event == 'Exit' or event == sg.WIN_CLOSED:
            break
        if event == '-PLACE-':
            query = values['-PLACE-']
            if debounce_timer:
                debounce_timer.cancel()
            debounce_timer = threading.Timer(debounce_time, lambda: window.write_event_value('-FETCH-', query))
            debounce_timer.start()
        if event == '-FETCH-':
            vm.place.set(values['-FETCH-'])
            places = vm.update_places()
            if places:
                window['-PLACES-'].update(values=places, visible=True)
            else:
                window['-PLACES-'].update(values=[], visible=False)
        if event == '-PLACES-':
            selected = values['-PLACES-'][0]
            window['-PLACES-'].update(visible=False)
            vm.update_all(selected)
        if event == 'Clear':
            window['-WEATHER-'].update('')
            window['-FORECAST-'].update('')
            window['-UV-'].update('')
            window['-HOUR-'].update('')
            window['-HISTORICAL-'].update('')
            window['-PLACE-'].update('')
            window['-PLACES-'].update(values=[], visible=False)

    window.close()


container = Container()

if __name__ == '__main__':
    container.register('weather_api', lambda: 'VIzofjD6GFsQnisLTFohqQ4vU6dlfq3E')
    container.register('WeatherModel', WeatherModel, container.get('weather_api'))
    container.register('WeatherViewModel', WeatherViewModel, container.get('WeatherModel'))
    main()
