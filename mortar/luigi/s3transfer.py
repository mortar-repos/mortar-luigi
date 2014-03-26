import luigi, abc
from luigi.parameter import Parameter
import datetime
from luigi import configuration, LocalTarget
from luigi.s3 import S3Target, S3PathTask, S3Client
from mortar.luigi import target_factory


"""
Generic task to move s3 to local target and vice-versa
    requires definition of input() and output()
"""
class S3TransferTask(luigi.Task):
    # s3 path to where file should be/go
    s3_path = Parameter()
    local_path = Parameter()
    file_name = Parameter()

    def get_s3_client(self):
        if not hasattr(self, "client"):
            self.client = S3Client(luigi.configuration.get_config().get('s3', 'aws_s3_access_key_id'), luigi.configuration.get_config().get('s3', 'aws_s3_secret_access_key'))
        return self.client

    def output(self):
        return [self.output_target()]

    @abc.abstractmethod
    def input_target(self):
        raise RuntimeError("Must implement input_target!")

    @abc.abstractmethod
    def output_target(self):
        raise RuntimeError("Must implement output_target!")

    def run(self):
        if not self.output()[0].exists():
            try:
                r = self.input_target().open('r')
                w = self.output_target().open('w')
                w.write(r.read())
                w.close()
            except:
                if self.output().exists(self.output_target().path):
                    self.output().remove()


class LocalToS3Task(S3TransferTask):

    def input_target(self):
        return LocalTarget(self.local_path + '/' + self.file_name)

    def output_target(self):
        return S3Target(self.s3_path + '/' + self.file_name, client=self.get_s3_client())


class S3ToLocalTask(S3TransferTask):

    def output_target(self):
        return LocalTarget(self.local_path + '/' + self.file_name)

    def input_target(self):
        return S3Target(self.s3_path + '/' + self.file_name, client=self.get_s3_client())


