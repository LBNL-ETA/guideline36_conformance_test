import BAC0

class Device:
    def __init__(self, device_config):
        self.device_config = device_config
        self.init_device(config=self.device_config)

    def init_device(self, config):
        self.network_address = config["network_address"]
        self.device_address = config["device_address"]
        self.device_id = config["device_id"]

        self.bacnet = BAC0.connect(ip=self.network_address)
        self.device = BAC0.device(address=self.device_address, device_id=self.device_id, network=self.bacnet, poll=5)
        self.point_properties = self.device.points_properties_df().T

    def get_point_properties(self):
        return self.point_properties

    def reset_device(self, object_list):
        self.device = BAC0.device(address=self.device_address, device_id=self.device_id, network=self.bacnet, poll=5,
                                  object_list=object_list)
        self.point_properties = self.device.points_properties_df().T

    def read_all_points(self):
        self.points = self.device.points

    def set_values(self, point_value_dict):
        for key in point_value_dict:
            try:
                self.device[key]  =point_value_dict[key]
            except:
                print("error with setting {}".format(key))

    # def read_data(self, points_to_read):
    #     '''
    #     Read values of requested points
    #     :param points_to_read: list of point names
    #     :return: dictionary of pointname: value
    #     '''
    #     # 1. find corresponding bacnet point names
    #     # 2. read points
    #     self.bacnet.readMultiple()

    def set_single_point(self, point_name, value):
        self.bacnet.write()