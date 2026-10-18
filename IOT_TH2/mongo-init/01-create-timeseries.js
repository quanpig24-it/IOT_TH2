db = db.getSiblingDB("iot_lab2");

const names = db.getCollectionNames();

if (!names.includes("sensor_raw")) {
  db.createCollection("sensor_raw", {
    timeseries: {
      timeField: "timestamp",
      metaField: "metadata",
      granularity: "seconds"
    }
  });
}

if (!db.getCollectionNames().includes("sensor_processed")) {
  db.createCollection("sensor_processed", {
    timeseries: {
      timeField: "timestamp",
      metaField: "metadata",
      granularity: "seconds"
    }
  });
}

db.sensor_raw.createIndex({ "metadata.device": 1, timestamp: -1 });
db.sensor_processed.createIndex({ "metadata.device": 1, timestamp: -1 });
print("MongoDB time-series collections ready: sensor_raw, sensor_processed");
