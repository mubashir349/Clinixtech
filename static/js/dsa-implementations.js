// dsa-implementations.js
// Data Structures and Algorithms implementations for patient portal

class PriorityQueue {
  constructor() {
    this.heap = [];
  }

  enqueue(item, priority) {
    this.heap.push({ item, priority });
    this.bubbleUp(this.heap.length - 1);
  }

  dequeue() {
    const min = this.heap[0];
    const end = this.heap.pop();
    if (this.heap.length > 0) {
      this.heap[0] = end;
      this.sinkDown(0);
    }
    return min ? min.item : null;
  }

  bubbleUp(index) {
    const element = this.heap[index];
    while (index > 0) {
      const parentIndex = Math.floor((index - 1) / 2);
      const parent = this.heap[parentIndex];
      if (element.priority >= parent.priority) break;
      this.heap[parentIndex] = element;
      this.heap[index] = parent;
      index = parentIndex;
    }
  }

  sinkDown(index) {
    const length = this.heap.length;
    const element = this.heap[index];

    while (true) {
      let leftChildIndex = 2 * index + 1;
      let rightChildIndex = 2 * index + 2;
      let swap = null;
      let leftChild, rightChild;

      if (leftChildIndex < length) {
        leftChild = this.heap[leftChildIndex];
        if (leftChild.priority < element.priority) {
          swap = leftChildIndex;
        }
      }

      if (rightChildIndex < length) {
        rightChild = this.heap[rightChildIndex];
        if (
          (swap === null && rightChild.priority < element.priority) ||
          (swap !== null && rightChild.priority < leftChild.priority)
        ) {
          swap = rightChildIndex;
        }
      }

      if (swap === null) break;
      this.heap[index] = this.heap[swap];
      this.heap[swap] = element;
      index = swap;
    }
  }

  isEmpty() {
    return this.heap.length === 0;
  }

  size() {
    return this.heap.length;
  }
}

class Graph {
  constructor() {
    this.nodes = new Map();
  }

  addNode(node) {
    this.nodes.set(node, []);
  }

  addEdge(node1, node2, weight) {
    this.nodes.get(node1).push({ node: node2, weight });
    this.nodes.get(node2).push({ node: node1, weight });
  }

  dijkstra(startNode) {
    const distances = new Map();
    const previous = new Map();
    const pq = new PriorityQueue();

    for (let node of this.nodes.keys()) {
      distances.set(node, node === startNode ? 0 : Infinity);
      previous.set(node, null);
      pq.enqueue(node, distances.get(node));
    }

    while (!pq.isEmpty()) {
      const currentNode = pq.dequeue();
      const neighbors = this.nodes.get(currentNode);

      for (let neighbor of neighbors) {
        const distance = distances.get(currentNode) + neighbor.weight;
        if (distance < distances.get(neighbor.node)) {
          distances.set(neighbor.node, distance);
          previous.set(neighbor.node, currentNode);
          pq.enqueue(neighbor.node, distance);
        }
      }
    }

    return { distances, previous };
  }
}

// Medical Data Analytics
class MedicalDataAnalyzer {
  constructor() {
    this.vitalsData = [];
    this.appointmentsData = [];
  }

  // Add vitals data
  addVitals(vitals) {
    this.vitalsData.push({
      date: new Date(vitals.date),
      heartRate: vitals.heart_rate,
      bloodPressure: {
        systolic: vitals.blood_pressure_systolic,
        diastolic: vitals.blood_pressure_diastolic,
      },
      temperature: vitals.temperature,
      oxygenSaturation: vitals.oxygen_saturation,
      weight: vitals.weight,
      bmi: vitals.bmi,
    });
  }

  // Add appointment data
  addAppointment(appointment) {
    this.appointmentsData.push({
      date: new Date(appointment.date),
      doctor: appointment.doctor,
      priority: appointment.priority,
      status: appointment.status,
    });
  }

  // Calculate trends for vitals
  calculateVitalsTrends(days = 30) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    const filteredData = this.vitalsData
      .filter((v) => v.date >= startDate && v.date <= endDate)
      .sort((a, b) => a.date - b.date);

    const trends = {
      heartRate: this.calculateLinearTrend(
        filteredData.map((v) => v.heartRate)
      ),
      weight: this.calculateLinearTrend(filteredData.map((v) => v.weight)),
      bmi: this.calculateLinearTrend(filteredData.map((v) => v.bmi)),
    };

    return trends;
  }

  // Linear regression trend calculation
  calculateLinearTrend(data) {
    const cleanData = data.filter((val) => val !== null && val !== undefined);
    const n = cleanData.length;

    if (n < 2) return { slope: 0, trend: "stable" };

    let sumX = 0,
      sumY = 0,
      sumXY = 0,
      sumX2 = 0;

    for (let i = 0; i < n; i++) {
      sumX += i;
      sumY += cleanData[i];
      sumXY += i * cleanData[i];
      sumX2 += i * i;
    }

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);

    let trend;
    if (Math.abs(slope) < 0.1) trend = "stable";
    else if (slope > 0) trend = "increasing";
    else trend = "decreasing";

    return { slope, trend };
  }

  // Predict health risk based on vitals
  predictHealthRisk() {
    const latestVitals = this.vitalsData[this.vitalsData.length - 1];
    if (!latestVitals) return "Unknown";

    let riskScore = 0;

    // Heart rate risk
    if (latestVitals.heartRate < 60 || latestVitals.heartRate > 100)
      riskScore += 2;
    else if (latestVitals.heartRate < 50 || latestVitals.heartRate > 120)
      riskScore += 3;

    // Blood pressure risk
    if (latestVitals.bloodPressure) {
      if (
        latestVitals.bloodPressure.systolic > 140 ||
        latestVitals.bloodPressure.diastolic > 90
      ) {
        riskScore += 2;
      }
    }

    // BMI risk
    if (latestVitals.bmi < 18.5 || latestVitals.bmi > 25) riskScore += 1;
    if (latestVitals.bmi < 16 || latestVitals.bmi > 30) riskScore += 2;

    if (riskScore >= 4) return "High";
    if (riskScore >= 2) return "Medium";
    return "Low";
  }

  // Appointment statistics
  getAppointmentStats() {
    const completed = this.appointmentsData.filter(
      (a) => a.status === "completed"
    ).length;
    const scheduled = this.appointmentsData.filter(
      (a) => a.status === "scheduled"
    ).length;
    const cancelled = this.appointmentsData.filter(
      (a) => a.status === "cancelled"
    ).length;
    const total = this.appointmentsData.length;

    return {
      completed,
      scheduled,
      cancelled,
      total,
      completionRate: total > 0 ? (completed / total) * 100 : 0,
    };
  }
}

// Visualization utilities
class DSAVisualizations {
  static createArrayVisualization(data, containerId, highlightIndex = -1) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";
    container.className = "array-visualization";

    data.forEach((value, index) => {
      const element = document.createElement("div");
      element.className = `array-element ${
        index === highlightIndex ? "highlight" : ""
      }`;
      element.textContent = value;
      element.title = `Index: ${index}, Value: ${value}`;
      container.appendChild(element);
    });
  }

  static createQueueVisualization(data, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";
    container.className = "queue-container";

    data.forEach((item, index) => {
      const queueItem = document.createElement("div");
      queueItem.className = "queue-item";
      queueItem.innerHTML = `
                <h6>${item.title}</h6>
                <p class="mb-1">${item.description}</p>
                <small class="text-muted">Priority: ${item.priority}</small>
            `;
      container.appendChild(queueItem);
    });
  }

  static createTreeVisualization(data, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = "";
    container.className = "tree-container";

    // Simple binary tree visualization
    function createNode(value, level = 0) {
      const node = document.createElement("div");
      node.className = "tree-node";
      node.textContent = value;
      node.style.marginLeft = `${level * 20}px`;
      return node;
    }

    // Example tree structure
    const root = createNode("Health Data");
    container.appendChild(root);

    if (data.vitals) {
      const vitalsNode = createNode("Vitals", 1);
      container.appendChild(vitalsNode);
    }

    if (data.appointments) {
      const appointmentsNode = createNode("Appointments", 1);
      container.appendChild(appointmentsNode);
    }
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Initialize medical data analyzer
  window.medicalAnalyzer = new MedicalDataAnalyzer();

  // Load sample data for demonstration
  loadSampleData();

  // Create visualizations if containers exist
  createDSAVisualizations();
});

function loadSampleData() {
  // Sample vitals data
  const sampleVitals = [
    {
      date: "2024-01-01",
      heart_rate: 72,
      blood_pressure_systolic: 120,
      blood_pressure_diastolic: 80,
      temperature: 98.6,
      weight: 70,
      bmi: 22.5,
    },
    {
      date: "2024-01-08",
      heart_rate: 75,
      blood_pressure_systolic: 118,
      blood_pressure_diastolic: 78,
      temperature: 98.4,
      weight: 69.5,
      bmi: 22.3,
    },
    {
      date: "2024-01-15",
      heart_rate: 71,
      blood_pressure_systolic: 122,
      blood_pressure_diastolic: 82,
      temperature: 98.7,
      weight: 70.2,
      bmi: 22.6,
    },
  ];

  sampleVitals.forEach((vital) => {
    window.medicalAnalyzer.addVitals(vital);
  });

  console.log("Sample medical data loaded");
}

function createDSAVisualizations() {
  // Array visualization
  const appointmentPriorities = [
    "Emergency",
    "Urgent",
    "Normal",
    "Normal",
    "Urgent",
  ];
  DSAVisualizations.createArrayVisualization(
    appointmentPriorities,
    "priorityArray"
  );

  // Queue visualization
  const appointmentQueue = [
    {
      title: "Cardiology Checkup",
      description: "Routine heart examination",
      priority: "Normal",
    },
    {
      title: "Emergency Visit",
      description: "Chest pain evaluation",
      priority: "Emergency",
    },
    {
      title: "Follow-up",
      description: "Medication review",
      priority: "Urgent",
    },
  ];
  DSAVisualizations.createQueueVisualization(
    appointmentQueue,
    "appointmentQueue"
  );

  // Tree visualization
  const healthDataTree = {
    vitals: true,
    appointments: true,
    prescriptions: true,
  };
  DSAVisualizations.createTreeVisualization(healthDataTree, "healthDataTree");
}

// Export for use in other modules
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    PriorityQueue,
    Graph,
    MedicalDataAnalyzer,
    DSAVisualizations,
  };
}
